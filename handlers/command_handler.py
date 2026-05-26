import functools
import html
import logging

import telebot
from telebot.types import Message

from config.settings import OWNER_ID
from database.conversations_repo import get_all_pending, get_today_stats
from database.settings_repo import get_active_connections, get_settings, set_setting
from database.templates_repo import delete_template, list_templates, upsert_template
from utils.formatting import format_status

_HELP_TEXT = (
    "🤖 <b>Business AI Bot</b>\n\n"
    "<b>Управление ботом:</b>\n"
    "  /status — статус и статистика за сегодня\n"
    "  /autoreply on|off — включить / выключить авто-ответ\n"
    "  /hours 09:00-18:00 — рабочие часы (авто-ответ вне них)\n"
    "  /hours off — убрать ограничение рабочих часов\n"
    "  /timezone +3 — часовой пояс (UTC±N)\n"
    "  /context — показать текущий контекст бизнеса\n"
    "  /context &lt;текст&gt; — задать контекст для AI\n"
    "  /pending — чаты, ожидающие твоего ответа\n\n"
    "<b>Шаблоны быстрых ответов:</b>\n"
    "  /template list\n"
    "  /template add &lt;name&gt; &lt;text&gt;\n"
    "  /template del &lt;name&gt;"
)


def _owner_only(func):
    @functools.wraps(func)
    def wrapper(message: Message):
        if message.from_user.id != OWNER_ID:
            return
        func(message)

    return wrapper


def register_command_handlers(bot: telebot.TeleBot) -> None:

    @bot.message_handler(commands=["start", "help"])
    @_owner_only
    def cmd_help(message: Message) -> None:
        bot.send_message(message.chat.id, _HELP_TEXT, parse_mode="HTML")

    @bot.message_handler(commands=["status"])
    @_owner_only
    def cmd_status(message: Message) -> None:
        settings = get_settings(OWNER_ID)
        connections = get_active_connections(OWNER_ID)
        connection = connections[0] if connections else None

        stats = get_today_stats(connection["connection_id"]) if connection else {}
        text = format_status(connection, settings, stats)
        bot.send_message(message.chat.id, text, parse_mode="HTML")

    @bot.message_handler(commands=["autoreply"])
    @_owner_only
    def cmd_autoreply(message: Message) -> None:
        parts = message.text.split()
        if len(parts) < 2 or parts[1].lower() not in ("on", "off"):
            bot.send_message(message.chat.id, "Использование: /autoreply on|off")
            return

        enabled = parts[1].lower() == "on"
        set_setting(OWNER_ID, "auto_reply", enabled)
        state = "включён 🟢" if enabled else "выключен 🔴"
        bot.send_message(message.chat.id, f"Авто-ответ {state}.")

    @bot.message_handler(commands=["hours"])
    @_owner_only
    def cmd_hours(message: Message) -> None:
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "Использование: /hours 09:00-18:00 или /hours off")
            return

        arg = parts[1].lower()

        if arg == "off":
            set_setting(OWNER_ID, "hours_start", None)
            set_setting(OWNER_ID, "hours_end", None)
            bot.send_message(message.chat.id, "Ограничение рабочих часов снято.")
            return

        if "-" not in arg:
            bot.send_message(message.chat.id, "Формат: /hours 09:00-18:00")
            return

        try:
            start_str, end_str = arg.split("-", 1)
            sh, sm = start_str.split(":")
            eh, em = end_str.split(":")
            assert 0 <= int(sh) <= 23 and 0 <= int(sm) <= 59
            assert 0 <= int(eh) <= 23 and 0 <= int(em) <= 59
        except Exception:
            bot.send_message(message.chat.id, "Неверный формат. Пример: /hours 09:00-18:00")
            return

        set_setting(OWNER_ID, "hours_start", start_str)
        set_setting(OWNER_ID, "hours_end", end_str)
        bot.send_message(
            message.chat.id,
            f"✅ Рабочие часы: {start_str} – {end_str}\n"
            f"Вне этих часов авто-ответ будет активироваться автоматически.",
        )

    @bot.message_handler(commands=["timezone"])
    @_owner_only
    def cmd_timezone(message: Message) -> None:
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "Использование: /timezone +3 или /timezone -5")
            return

        try:
            offset_hours = float(parts[1].replace(",", "."))
            offset_min = int(offset_hours * 60)
            if not (-12 * 60 <= offset_min <= 14 * 60):
                raise ValueError
        except ValueError:
            bot.send_message(message.chat.id, "Неверный формат. Пример: /timezone +3")
            return

        set_setting(OWNER_ID, "tz_offset_minutes", offset_min)
        sign = "+" if offset_hours >= 0 else ""
        bot.send_message(message.chat.id, f"✅ Часовой пояс: UTC{sign}{offset_hours:.4g}")

    @bot.message_handler(commands=["context"])
    @_owner_only
    def cmd_context(message: Message) -> None:
        arg = message.text[len("/context"):].strip()

        if not arg or arg.lower() == "show":
            settings = get_settings(OWNER_ID)
            ctx = settings.get("business_context")
            if ctx:
                bot.send_message(
                    message.chat.id,
                    f"<b>Контекст бизнеса:</b>\n\n{html.escape(ctx)}",
                    parse_mode="HTML",
                )
            else:
                bot.send_message(
                    message.chat.id,
                    "Контекст не задан.\n\nИспользуй /context &lt;текст&gt; для установки.\n\n"
                    "<i>Пример: /context Я владею фотостудией в Москве. "
                    "Специализируюсь на портретах и событиях. "
                    "Цены: портреты от 5000 руб, события от 15000 руб.</i>",
                    parse_mode="HTML",
                )
            return

        if len(arg) > 3000:
            bot.send_message(message.chat.id, "Слишком длинный текст (максимум 3000 символов).")
            return

        set_setting(OWNER_ID, "business_context", arg)
        bot.send_message(message.chat.id, "✅ Контекст бизнеса сохранён.")

    @bot.message_handler(commands=["pending"])
    @_owner_only
    def cmd_pending(message: Message) -> None:
        pending = get_all_pending()
        if not pending:
            bot.send_message(message.chat.id, "✅ Нет чатов, ожидающих ответа.")
            return

        lines = ["⏳ <b>Ожидают ответа:</b>\n"]
        for conv in pending[:20]:
            name = html.escape(conv["user_name"] or "Неизвестный")
            uname = f" @{html.escape(conv['username'])}" if conv["username"] else ""
            lines.append(f"• {name}{uname}")

        if len(pending) > 20:
            lines.append(f"\n<i>...и ещё {len(pending) - 20}</i>")

        bot.send_message(message.chat.id, "\n".join(lines), parse_mode="HTML")

    @bot.message_handler(commands=["template"])
    @_owner_only
    def cmd_template(message: Message) -> None:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 2:
            bot.send_message(
                message.chat.id,
                "Команды шаблонов:\n"
                "  /template list\n"
                "  /template add &lt;name&gt; &lt;text&gt;\n"
                "  /template del &lt;name&gt;",
                parse_mode="HTML",
            )
            return

        subcmd = parts[1].lower()

        if subcmd == "list":
            templates = list_templates(OWNER_ID)
            if not templates:
                bot.send_message(
                    message.chat.id,
                    "Шаблонов нет. Добавь: /template add &lt;name&gt; &lt;text&gt;",
                    parse_mode="HTML",
                )
                return
            lines = ["📝 <b>Шаблоны:</b>\n"]
            for t in templates:
                preview = html.escape(t["text"][:80]) + ("..." if len(t["text"]) > 80 else "")
                lines.append(f"<b>{html.escape(t['name'])}</b>: {preview}")
            bot.send_message(message.chat.id, "\n".join(lines), parse_mode="HTML")

        elif subcmd == "add":
            if len(parts) < 3:
                bot.send_message(
                    message.chat.id,
                    "Использование: /template add &lt;name&gt; &lt;text&gt;",
                    parse_mode="HTML",
                )
                return
            rest = parts[2].split(maxsplit=1)
            if len(rest) < 2:
                bot.send_message(message.chat.id, "Укажи имя и текст шаблона.")
                return
            name, text = rest[0].lower(), rest[1]
            upsert_template(OWNER_ID, name, text)
            bot.send_message(
                message.chat.id,
                f"✅ Шаблон <b>{html.escape(name)}</b> сохранён.",
                parse_mode="HTML",
            )

        elif subcmd == "del":
            if len(parts) < 3:
                bot.send_message(
                    message.chat.id,
                    "Использование: /template del &lt;name&gt;",
                    parse_mode="HTML",
                )
                return
            name = parts[2].strip().lower()
            if delete_template(OWNER_ID, name):
                bot.send_message(
                    message.chat.id,
                    f"🗑️ Шаблон <b>{html.escape(name)}</b> удалён.",
                    parse_mode="HTML",
                )
            else:
                bot.send_message(
                    message.chat.id,
                    f"Шаблон <b>{html.escape(name)}</b> не найден.",
                    parse_mode="HTML",
                )

        else:
            bot.send_message(message.chat.id, "Неизвестная подкоманда. Доступно: list, add, del")
