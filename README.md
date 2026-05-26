# Telegram Business AI Bot

An AI-powered assistant for [Telegram Business](https://telegram.org/blog/telegram-business) accounts. The bot receives messages sent to your Telegram account and can automatically reply on your behalf using Groq AI — while keeping you notified of every conversation.

## Table of Contents

- [How It Works](#how-it-works)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
- [Running the Bot](#running-the-bot)
  - [Docker (local development)](#docker-local-development)
  - [Raspberry Pi (systemd service)](#raspberry-pi-systemd-service)
- [Connecting to Your Telegram Account](#connecting-to-your-telegram-account)
- [Owner Commands](#owner-commands)
- [Auto-Reply Logic](#auto-reply-logic)
- [Quick Reply Templates](#quick-reply-templates)
- [Project Structure](#project-structure)

---

## How It Works

Telegram Business allows a bot to be connected to a personal Telegram account. Once connected:

1. Every message sent to your account is also delivered to the bot as a `business_message` update.
2. The bot can reply to those messages on your behalf using `sendMessage` with `business_connection_id` — the reply appears as if you sent it.
3. You (the owner) receive a notification in your private chat with the bot for every incoming message, with quick-action buttons.

---

## Features

- **AI auto-reply** — Groq AI generates responses on your behalf using your configured business context and per-contact conversation history
- **Business hours** — auto-reply activates automatically outside your working hours; during hours it only notifies you
- **Message classification** — each incoming message is classified as inquiry / order / complaint / spam / greeting, shown in the owner notification
- **Per-contact memory** — conversation history is stored per customer chat and included in AI context
- **Quick reply templates** — save and send pre-written responses with one tap
- **Owner notifications** — every incoming message triggers a formatted alert with inline action buttons
- **One-tap actions** — send a template or trigger an AI reply directly from the notification without opening the chat

---

## Prerequisites

- A Telegram bot token from [@BotFather](https://t.me/BotFather) with **Business Mode enabled** (BotFather → your bot → Bot Settings → Business Mode → Turn on)
- A [Groq API key](https://console.groq.com)
- Your Telegram user ID (get it from [@userinfobot](https://t.me/userinfobot))
- A Telegram Premium account (required for Telegram Business features)
- Docker + Docker Compose **or** Python 3.11+ for direct execution

---

## Configuration

Copy the example environment file and fill in the values:

```bash
cp .env.example .env
```

```env
BOT_TOKEN=your_bot_token_here
OWNER_ID=your_telegram_user_id_here
GROQ_API_KEY=your_groq_api_key_here
LOG_LEVEL=INFO
```

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Telegram bot token from @BotFather |
| `OWNER_ID` | Your Telegram user ID — only this user can control the bot |
| `GROQ_API_KEY` | Groq API key for AI inference |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` (default: `INFO`) |

---

## Running the Bot

### Docker (local development)

```bash
# Build and start
docker compose up --build

# Run in background
docker compose up -d --build

# View logs
docker compose logs -f

# Stop
docker compose down
```

The SQLite database is persisted in `./data/business_bot.db` via a Docker volume mount.

### Raspberry Pi (systemd service)

**1. Clone the repository and create a virtual environment:**

```bash
git clone <repo-url> ~/telegram-business-ai-bot
cd ~/telegram-business-ai-bot
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

**2. Create the `.env` file:**

```bash
cp .env.example .env
nano .env
```

**3. Install and enable the systemd service:**

```bash
sudo cp telegram-business-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable telegram-business-bot
sudo systemctl start telegram-business-bot
```

**4. Useful service commands:**

```bash
# Check status
sudo systemctl status telegram-business-bot

# View live logs
sudo journalctl -u telegram-business-bot -f

# Restart after code changes
sudo systemctl restart telegram-business-bot
```

> The service file assumes the repo is at `/home/mik/telegram-business-ai-bot` and the user is `mik`. Edit `telegram-business-bot.service` if your paths differ.

---

## Connecting to Your Telegram Account

1. Start a private chat with your bot and send `/start`
2. Open Telegram → **Settings → Telegram Business → Chatbots**
3. Search for your bot and connect it
4. Send `/status` in the bot chat to verify the connection is active

> **Note:** Your bot must have Business Mode enabled in BotFather settings before it appears in the chatbot search.

---

## Owner Commands

All commands are sent in your **private chat with the bot**.

### Bot management

| Command | Description |
|---|---|
| `/status` | Connection status and today's message stats |
| `/autoreply on\|off` | Manually enable or disable auto-reply |
| `/hours 09:00-18:00` | Set working hours (auto-reply activates outside them) |
| `/hours off` | Remove working hours restriction |
| `/timezone +3` | Set your UTC offset (e.g. `+3`, `-5`, `+5.5`) |
| `/context <text>` | Set business context for the AI (who you are, your communication style) |
| `/context` | Show current context |
| `/pending` | List customer chats waiting for a reply |

### Templates

| Command | Description |
|---|---|
| `/template list` | Show all saved templates |
| `/template add <name> <text>` | Add or update a template |
| `/template del <name>` | Delete a template |

**Example — setting up context:**
```
/context My name is Michael. I reply briefly and to the point.
I communicate with colleagues and clients. Informal tone.
If I don't know the answer I say I'll get back to them.
```

---

## Auto-Reply Logic

Auto-reply fires when **either** condition is true:

- `/autoreply on` is set (always on), **or**
- The current time is **outside** the configured business hours

When auto-reply fires:
1. The last 15 messages from the conversation are loaded as context
2. Groq (`llama-3.3-70b-versatile`) generates a reply using your business context
3. The reply is sent to the customer via the Telegram Business API
4. The chat is marked as not pending

When auto-reply does **not** fire (within business hours with `autoreply off`), you receive a notification with an **"Auto-reply now"** button to trigger it manually.

Message classification (powered by `llama-3.1-8b-instant`) determines the emoji and label shown in the notification:

| Classification | Emoji | Trigger |
|---|---|---|
| Inquiry | 💬 | Questions about products, services, pricing |
| Order | 🛒 | Purchase or booking requests |
| Complaint | 🔴 | Dissatisfaction or problem reports |
| Greeting | 👋 | Simple greetings or small talk |
| Spam | 🗑️ | Irrelevant or automated messages |
| Other | 📨 | Anything else |

---

## Quick Reply Templates

Templates let you send a pre-written response to any customer chat with one tap.

```bash
# Add a template
/template add hello Hi! Thanks for reaching out, I'll get back to you shortly.

# Add a multi-word template name using underscore
/template add out_of_office I'm currently unavailable. I'll reply within 24 hours.
```

When a customer message arrives, tap **📝 Template** in the notification → select a template → it's sent instantly.

---

## Project Structure

```
├── main.py                      # Entry point, polling loop
├── config/settings.py           # Environment variables and constants
├── core/
│   ├── brain.py                 # Groq API calls (generate_reply, classify_message)
│   └── prompts.py               # AI system prompts
├── handlers/
│   ├── business_handler.py      # business_connection + business_message updates
│   ├── command_handler.py       # Owner slash commands
│   └── callback_handler.py      # Inline button callbacks
├── database/
│   ├── db.py                    # SQLite init and schema
│   ├── conversations_repo.py    # Conversation history and message log
│   ├── templates_repo.py        # Quick reply templates
│   └── settings_repo.py         # Owner settings and connection state
├── services/telegram_service.py # Bot initialization, handler registration
├── utils/
│   ├── formatting.py            # Notification formatting (HTML-safe)
│   └── hours.py                 # Business hours check with UTC offset
├── data/                        # SQLite database (gitignored)
├── Dockerfile
├── docker-compose.yml
└── telegram-business-bot.service  # systemd unit for Raspberry Pi
```
