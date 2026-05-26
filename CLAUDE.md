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

## Architecture

This is a **Telegram Business Bot** — it receives `business_message` updates (messages sent to the owner's Telegram account) and can auto-reply on the owner's behalf using Groq AI. Unlike a regular bot, replies go out via `bot.send_message(..., business_connection_id=conn_id)`, not to the bot's own chat.

### Data flow for incoming customer messages

1. `handlers/business_handler.py` receives `business_message`
2. Checks if the sender is the owner (if so, just marks chat as not pending and returns)
3. Decides whether to auto-reply based on `owner_settings.auto_reply` OR whether current time is outside configured business hours (`utils/hours.py`)
4. If auto-replying: calls `core/brain.py → generate_reply()` → sends via Telegram API with `business_connection_id`
5. Always classifies the message (`classify_message()`) and notifies the owner with inline buttons

### Single-owner design

`OWNER_ID` (env var) is the only Telegram user who can run commands and receive notifications. Business connections from other users are rejected in `on_business_connection`. All settings in the DB are keyed by `owner_id`.

### Database (SQLite)

Five tables in `data/business_bot.db`, all managed through repo modules:
- `business_connections` — active Telegram Business connection IDs and `can_reply` flag
- `conversations` — one row per customer chat, tracks `is_pending`
- `messages` — full message log; roles are `user` (customer), `assistant` (bot auto-reply), `owner` (owner's own reply)
- `templates` — owner's saved quick-reply texts
- `owner_settings` — auto_reply flag, business hours (`hours_start`/`hours_end` as `"HH:MM"`), `tz_offset_minutes`, and `business_context` text

`database/settings_repo.py::set_setting()` uses an f-string for the column name but only after validating against `_ALLOWED_SETTINGS` whitelist — this is intentional and safe.

### Groq AI (`core/brain.py`)

- `generate_reply()` — uses `llama-3.3-70b-versatile`, builds messages array from conversation history, maps DB roles `owner`/`assistant` → Groq `assistant` role, `user` → Groq `user` role
- `classify_message()` — uses `llama-3.1-8b-instant` (fast model), returns one of: `inquiry`, `order`, `complaint`, `spam`, `greeting`, `other`

### Adding new owner commands

Register in `handlers/command_handler.py` with the `@_owner_only` decorator (silently ignores non-owner users). All DB writes go through the repo layer, never direct SQL in handlers.

### Callback data format

Inline button callback data uses `:` as separator with a short prefix:
- `tpl_list:{chat_id}:{conn_id}` — show template picker
- `tpl_send:{template_id}:{chat_id}:{conn_id}` — send a specific template
- `ar_now:{chat_id}:{conn_id}` — generate and send AI reply immediately
