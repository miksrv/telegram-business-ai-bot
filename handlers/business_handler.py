import logging

import telebot

from config.settings import OWNER_ID
from core.brain import analyze_style, classify_message, generate_reply
from database.conversations_repo import (
    get_conversation_history,
    get_message_count,
    mark_not_pending,
    save_message,
    upsert_conversation,
)
from database.settings_repo import get_connection, get_settings, upsert_connection
from database.style_repo import get_contact_style, save_contact_style
from database.templates_repo import list_templates
from utils.formatting import (
    build_notification_keyboard,
    format_notification,
    format_user_name,
)
from utils.hours import is_within_business_hours

# Minimum total messages in a conversation before style analysis is attempted
_MIN_MSGS_FOR_STYLE = 5
# Re-analyze style every N new messages to evolve with the relationship
_STYLE_REANALYSIS_INTERVAL = 20


def _get_or_refresh_style(conn_id: str, chat_id: int) -> str | None:
    """
    Returns cached style for this contact, refreshing it when needed.
    Analysis is skipped silently if there aren't enough messages yet.
    """
    style_row = get_contact_style(chat_id)
    current_count = get_message_count(conn_id, chat_id)

    analyzed_count = style_row["msg_count"] if style_row else 0
    needs_analysis = (
        style_row is None and current_count >= _MIN_MSGS_FOR_STYLE
    ) or (
        style_row is not None
        and current_count - analyzed_count >= _STYLE_REANALYSIS_INTERVAL
    )

    if not needs_analysis:
        return style_row["style_summary"] if style_row else None

    # Fetch a broader history window for analysis (not capped at 15)
    history = get_conversation_history(conn_id, chat_id, limit=30)
    new_style = analyze_style(history)

    if new_style:
        save_contact_style(chat_id, conn_id, new_style, current_count)
        logging.info(
            "Contact style %s for chat %d (%d msgs)",
            "updated" if style_row else "created",
            chat_id,
            current_count,
        )
        return new_style

    return style_row["style_summary"] if style_row else None


def register_business_handlers(bot: telebot.TeleBot) -> None:

    @bot.business_connection_handler()
    def on_business_connection(bc: telebot.types.BusinessConnection) -> None:
        if bc.user.id != OWNER_ID:
            logging.warning("Business connection from unknown user %d, ignoring", bc.user.id)
            return

        upsert_connection(
            connection_id=bc.id,
            owner_id=bc.user.id,
            owner_chat_id=bc.user_chat_id,
            can_reply=bc.can_reply,
            is_active=bc.is_enabled,
        )

        if bc.is_enabled:
            bot.send_message(
                OWNER_ID,
                f"✅ <b>Бот подключён к бизнес-аккаунту</b>\n"
                f"ID подключения: <code>{bc.id}</code>\n"
                f"Может отвечать: {'да' if bc.can_reply else 'нет'}\n\n"
                f"Используй /help для просмотра доступных команд.",
                parse_mode="HTML",
            )
            logging.info("Business connection activated: %s", bc.id)
        else:
            bot.send_message(
                OWNER_ID,
                f"❌ <b>Бизнес-подключение отключено</b>\n"
                f"ID: <code>{bc.id}</code>",
                parse_mode="HTML",
            )
            logging.info("Business connection deactivated: %s", bc.id)

    @bot.business_message_handler(
        content_types=["text", "photo", "sticker", "voice", "video", "document", "audio"]
    )
    def on_business_message(message: telebot.types.Message) -> None:
        conn_id = message.business_connection_id
        chat_id = message.chat.id
        sender_id = message.from_user.id
        text = message.text or message.caption or ""

        connection = get_connection(conn_id)
        if not connection or not connection["is_active"]:
            return

        owner_id = connection["owner_id"]

        # Owner replied directly in this business chat — clear pending, track message
        if sender_id == owner_id:
            if text:
                save_message(conn_id, chat_id, "owner", text)
            mark_not_pending(conn_id, chat_id)
            return

        # Incoming customer message
        user_name = format_user_name(message.from_user)
        upsert_conversation(
            conn_id, chat_id, sender_id, user_name, message.from_user.username, pending=True
        )
        if text:
            save_message(conn_id, chat_id, "user", text)

        settings = get_settings(owner_id)
        within_hours = is_within_business_hours(
            settings.get("hours_start"),
            settings.get("hours_end"),
            settings.get("tz_offset_minutes", 0),
        )

        should_auto_reply = (
            bool(text)
            and connection["can_reply"]
            and (settings.get("auto_reply") or not within_hours)
        )

        auto_replied = False
        ai_failed = False
        if should_auto_reply:
            contact_style = _get_or_refresh_style(conn_id, chat_id)
            history = get_conversation_history(conn_id, chat_id)
            try:
                reply = generate_reply(
                    text, history, settings.get("business_context"), contact_style
                )
            except Exception as e:
                logging.error("generate_reply raised unexpectedly for chat %d: %s", chat_id, e)
                reply = None

            if reply:
                try:
                    bot.send_message(chat_id, reply, business_connection_id=conn_id)
                    save_message(conn_id, chat_id, "assistant", reply)
                    mark_not_pending(conn_id, chat_id)
                    auto_replied = True
                    logging.info("Auto-replied to chat %d via connection %s", chat_id, conn_id)
                except Exception as e:
                    logging.error("Failed to send auto-reply to %d: %s", chat_id, e)
            else:
                ai_failed = True

        classification = classify_message(text) if text else "other"
        templates = list_templates(owner_id)

        notification = format_notification(
            message.from_user,
            text or "[нетекстовое сообщение]",
            classification,
            auto_replied,
            ai_failed=ai_failed,
        )
        keyboard = build_notification_keyboard(chat_id, conn_id, auto_replied, bool(templates))

        try:
            bot.send_message(
                owner_id,
                notification,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        except Exception as e:
            logging.error("Failed to notify owner: %s", e)

    @bot.edited_business_message_handler(content_types=["text"])
    def on_edited_business_message(message: telebot.types.Message) -> None:
        logging.debug(
            "Edited business message in chat %d (connection %s)",
            message.chat.id,
            message.business_connection_id,
        )

    @bot.deleted_business_messages_handler()
    def on_deleted_business_messages(
        deleted: telebot.types.BusinessMessagesDeleted,
    ) -> None:
        logging.debug(
            "Deleted %d messages in chat %d (connection %s)",
            len(deleted.message_ids),
            deleted.chat.id,
            deleted.business_connection_id,
        )
