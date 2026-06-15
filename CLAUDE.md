# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the bot

```bash
# Local development (Docker)
docker compose up --build

# Direct (requires venv with requirements.txt installed)
python main.py

# Raspberry Pi (systemd)
sudo systemctl start telegram-business-bot
sudo journalctl -u telegram-business-bot -f
```

Copy `.env.example` to `.env` and fill in `BOT_TOKEN`, `GROQ_API_KEY`, `OWNER_ID` before running.
Optional: `LOG_LEVEL` (default `INFO`).

## Architecture

This is a **Telegram Business Bot** — it receives `business_message` updates (messages sent to the owner's Telegram account) and can auto-reply on the owner's behalf using Groq AI. Unlike a regular bot, replies go out via `bot.send_message(..., business_connection_id=conn_id)`, not to the bot's own chat.

It uses **pyTelegramBotAPI (`telebot`)** in long-polling mode (no webhooks). `main.py` runs `bot.infinity_polling()` inside a crash-restart loop with `allowed_updates` scoped to message/callback/business updates, plus SIGINT/SIGTERM handlers that close the DB cleanly.

### Module layout

- `main.py` — entrypoint: logging setup, signal handlers, `init_db()`, `init_bot()`, polling loop
- `config/settings.py` — env loading via `require_env()`, model IDs, and limit constants
- `services/telegram_service.py` — `init_bot()` constructs the `TeleBot` and registers all three handler groups
- `handlers/` — `business_handler.py` (incoming business updates), `command_handler.py` (owner slash commands), `callback_handler.py` (inline-button callbacks)
- `core/brain.py` — Groq API calls; `core/prompts.py` — all prompt templates
- `database/` — `db.py` (connection + schema) and one repo module per concern
- `utils/` — `hours.py` (business-hours check), `formatting.py` (notification/status text + keyboards)

### Data flow for incoming customer messages

1. `handlers/business_handler.py::on_business_message` receives `business_message`
2. Looks up the connection; ignores it if missing or `is_active` is false
3. If the sender is the owner: saves the text as an `owner` message, marks chat not pending, returns
4. Otherwise upserts the conversation (pending) and saves the customer message
5. Decides whether to auto-reply: requires non-empty text AND `connection.can_reply` AND (`owner_settings.auto_reply` OR current time is outside configured business hours via `utils/hours.py`)
6. If auto-replying: resolves the contact's writing style (`_get_or_refresh_style`), calls `core/brain.py::generate_reply()`, sends via Telegram API with `business_connection_id`, saves the reply as an `assistant` message
7. Always classifies the message (`classify_message()`) and notifies the owner with an inline keyboard. The notification status reflects auto-replied / AI-failed / awaiting-reply.

`edited_business_message` and `deleted_business_messages` updates are handled but only logged.

### Contact-style learning

The bot adapts its tone per contact. `business_handler._get_or_refresh_style()` reads the cached style from `contact_styles`, and (re)analyzes via `core/brain.py::analyze_style()` when:
- there is no cached style yet and the conversation has ≥ 5 messages (`_MIN_MSGS_FOR_STYLE`), or
- ≥ 20 new messages (`_STYLE_REANALYSIS_INTERVAL`) have arrived since the last analysis.

`analyze_style()` needs ≥ 2 owner/assistant turns (`_MIN_OWNER_REPLIES_FOR_STYLE`), uses the fast model, and returns a short style summary that is injected into the reply system prompt.

### Single-owner design

`OWNER_ID` (env var) is the only Telegram user who can run commands and receive notifications. Business connections from other users are rejected in `on_business_connection`. Settings, templates, and connections in the DB are keyed by `owner_id`.

### Database (SQLite)

Six tables in `data/business_bot.db`, all managed through repo modules (never write raw SQL in handlers):
- `business_connections` — Telegram Business connection IDs with `can_reply` and `is_active` flags + `owner_chat_id` (`settings_repo.py`)
- `conversations` — one row per customer chat, tracks `is_pending`, `message_count`, user name/username (`conversations_repo.py`)
- `messages` — full message log; roles are `user` (customer), `assistant` (bot auto-reply / template), `owner` (owner's own reply) (`conversations_repo.py`)
- `contact_styles` — per-chat learned writing-style summary + `msg_count` at last analysis (`style_repo.py`)
- `templates` — owner's saved quick-reply texts (`templates_repo.py`)
- `owner_settings` — `auto_reply` flag, business hours (`hours_start`/`hours_end` as `"HH:MM"`), `tz_offset_minutes`, and `business_context` text (`settings_repo.py`)

`database/settings_repo.py::set_setting()` uses an f-string for the column name but only after validating against the `_ALLOWED_SETTINGS` whitelist — this is intentional and safe. `db.py` keeps a single module-level connection (`check_same_thread=False`) shared across telebot's worker threads.

### Groq AI (`core/brain.py`)

All calls go through `_call_groq()`, which posts to the Groq OpenAI-compatible endpoint using a shared `requests.Session` with a urllib3 `Retry` adapter (network retries) plus explicit handling/logging of HTTP 429/402/401/403. On any failure it returns `None` so the caller can fall back gracefully (no reply sent, owner notified). Model IDs and limits live in `config/settings.py`.

- `generate_reply()` — uses `MODEL_TEXT` (`llama-3.3-70b-versatile`); builds a messages array from the last `MAX_HISTORY_MESSAGES` (15) history rows, mapping DB roles `owner`/`assistant` → Groq `assistant`, `user` → Groq `user`. Takes optional `business_context` and `contact_style`, both injected into the system prompt. The prompt enforces a **strict grounding rule**: only answer from the provided business context, otherwise defer ("I'll get back to you shortly").
- `analyze_style()` — uses `MODEL_FAST` (`llama-3.1-8b-instant`); returns a 2–4 sentence style guide for one contact.
- `classify_message()` — uses `MODEL_FAST`; returns one of: `inquiry`, `order`, `complaint`, `spam`, `greeting`, `other` (validated against a whitelist, defaults to `other`).

Prompt text is centralized in `core/prompts.py` (`get_business_reply_prompt`, `get_style_analysis_prompt`, `get_classification_prompt`).

### Owner commands

Registered in `handlers/command_handler.py` with the `@_owner_only` decorator (silently ignores non-owner users):
- `/start`, `/help` — help text
- `/status` — connection status + today's stats
- `/autoreply on|off` — toggle auto-reply
- `/hours 09:00-18:00` / `/hours off` — set or clear business hours (auto-reply activates outside them; overnight spans supported)
- `/timezone +3` — UTC offset (accepts fractional hours)
- `/context [<text>]` — show or set the business context (max 3000 chars)
- `/pending` — list chats awaiting a reply
- `/template list|add <name> <text>|del <name>` — manage quick-reply templates

When adding a command, register it in `command_handler.py` with `@_owner_only` and route all DB writes through the repo layer.

### Inline callbacks (`handlers/callback_handler.py`)

Callback data uses `:` as separator with a short prefix:
- `tpl_list:{chat_id}:{conn_id}` — show template picker
- `tpl_send:{template_id}:{chat_id}:{conn_id}` — send a specific template
- `ar_now:{chat_id}:{conn_id}` — generate and send an AI reply immediately
- `cancel` — dismiss the inline keyboard

The notification keyboard is built in `utils/formatting.py::build_notification_keyboard` (Template button only if templates exist; Auto-reply button only if not already auto-replied). All callbacks re-check `from_user.id == OWNER_ID` and the connection's `can_reply` flag.
