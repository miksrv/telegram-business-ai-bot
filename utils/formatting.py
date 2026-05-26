import html

from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

CLASSIFICATION_EMOJI = {
    "inquiry": "💬",
    "order": "🛒",
    "complaint": "🔴",
    "spam": "🗑️",
    "greeting": "👋",
    "other": "📨",
}

CLASSIFICATION_LABEL = {
    "inquiry": "Запрос",
    "order": "Заказ",
    "complaint": "Жалоба ⚠️",
    "spam": "Спам",
    "greeting": "Приветствие",
    "other": "Сообщение",
}


def format_user_name(from_user) -> str:
    name = from_user.first_name or ""
    if from_user.last_name:
        name += f" {from_user.last_name}"
    return name.strip() or "Неизвестный"


def format_notification(from_user, text: str, classification: str, auto_replied: bool) -> str:
    emoji = CLASSIFICATION_EMOJI.get(classification, "📨")
    label = CLASSIFICATION_LABEL.get(classification, "Сообщение")

    name = html.escape(format_user_name(from_user))
    username_str = f" @{html.escape(from_user.username)}" if from_user.username else ""

    preview = html.escape(text[:300]) + ("..." if len(text) > 300 else "")
    status = "✅ Авто-ответ отправлен" if auto_replied else "⏳ Ожидает ответа"

    return (
        f"{emoji} <b>{name}{username_str}</b>\n"
        f"<i>{label}</i>\n"
        f"─────────────────────\n"
        f"{preview}\n"
        f"─────────────────────\n"
        f"{status}"
    )


def build_notification_keyboard(
    chat_id: int,
    conn_id: str,
    auto_replied: bool,
    has_templates: bool,
) -> InlineKeyboardMarkup | None:
    buttons = []

    if has_templates:
        buttons.append(
            InlineKeyboardButton("📝 Шаблон", callback_data=f"tpl_list:{chat_id}:{conn_id}")
        )

    if not auto_replied:
        buttons.append(
            InlineKeyboardButton("🤖 Авто-ответить", callback_data=f"ar_now:{chat_id}:{conn_id}")
        )

    if not buttons:
        return None

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(*buttons)
    return kb


def format_status(connection, settings: dict, stats: dict) -> str:
    if connection and connection["is_active"]:
        conn_status = f"✅ Активно"
        can_reply = "🟢 может отвечать" if connection["can_reply"] else "🔴 только чтение"
    else:
        conn_status = "❌ Нет подключения"
        can_reply = ""

    ar_status = "🟢 Включён" if settings.get("auto_reply") else "🔴 Выключен"

    if settings.get("hours_start") and settings.get("hours_end"):
        offset = settings.get("tz_offset_minutes", 0)
        hours_val = offset / 60
        sign = "+" if hours_val >= 0 else ""
        tz_str = f"UTC{sign}{hours_val:.4g}"
        hours = f"{settings['hours_start']} – {settings['hours_end']} ({tz_str})"
    else:
        hours = "не настроены (авто-ответ не зависит от времени)"

    context = "✅ Задан" if settings.get("business_context") else "❌ Не задан"

    lines = [
        "🤖 <b>Business Bot Status</b>",
        "─────────────────────",
        f"Подключение: {conn_status}" + (f" — {can_reply}" if can_reply else ""),
        f"Авто-ответ: {ar_status}",
        f"Рабочие часы: {hours}",
        f"Контекст бизнеса: {context}",
        "─────────────────────",
        "📊 <b>Сегодня:</b>",
        f"  • Получено сообщений: {stats.get('received', 0)}",
        f"  • Авто-ответов отправлено: {stats.get('sent', 0)}",
        f"  • Ожидают ответа: {stats.get('pending', 0)}",
    ]
    return "\n".join(lines)
