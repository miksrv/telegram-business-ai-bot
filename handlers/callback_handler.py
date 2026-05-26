import logging

import telebot
from telebot.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from config.settings import OWNER_ID
from core.brain import generate_reply
from database.conversations_repo import (
    get_conversation_history,
    mark_not_pending,
    save_message,
)
from database.settings_repo import get_connection, get_settings
from database.templates_repo import get_template_by_id, list_templates


def register_callback_handlers(bot: telebot.TeleBot) -> None:

    @bot.callback_query_handler(func=lambda c: c.data.startswith("tpl_list:"))
    def on_template_list(call: CallbackQuery) -> None:
        if call.from_user.id != OWNER_ID:
            bot.answer_callback_query(call.id)
            return

        _, chat_id_str, conn_id = call.data.split(":", 2)
        chat_id = int(chat_id_str)

        templates = list_templates(OWNER_ID)
        if not templates:
            bot.answer_callback_query(call.id, "Шаблонов нет. Добавь через /template add")
            return

        kb = InlineKeyboardMarkup()
        for t in templates[:10]:
            kb.add(
                InlineKeyboardButton(
                    t["name"],
                    callback_data=f"tpl_send:{t['id']}:{chat_id}:{conn_id}",
                )
            )
        kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))

        try:
            bot.edit_message_reply_markup(
                call.message.chat.id, call.message.message_id, reply_markup=kb
            )
        except Exception:
            pass
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("tpl_send:"))
    def on_template_send(call: CallbackQuery) -> None:
        if call.from_user.id != OWNER_ID:
            bot.answer_callback_query(call.id)
            return

        parts = call.data.split(":", 3)
        template_id = int(parts[1])
        chat_id = int(parts[2])
        conn_id = parts[3]

        template = get_template_by_id(template_id)
        if not template:
            bot.answer_callback_query(call.id, "Шаблон не найден")
            return

        connection = get_connection(conn_id)
        if not connection or not connection["can_reply"]:
            bot.answer_callback_query(call.id, "Нет активного подключения или нет прав отвечать")
            return

        try:
            bot.send_message(chat_id, template["text"], business_connection_id=conn_id)
            save_message(conn_id, chat_id, "assistant", template["text"])
            mark_not_pending(conn_id, chat_id)
            bot.answer_callback_query(call.id, f"✅ Шаблон «{template['name']}» отправлен")
            bot.edit_message_reply_markup(
                call.message.chat.id, call.message.message_id, reply_markup=None
            )
        except Exception as e:
            logging.error("Template send failed (chat=%d): %s", chat_id, e)
            bot.answer_callback_query(call.id, "Ошибка при отправке")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ar_now:"))
    def on_autoreply_now(call: CallbackQuery) -> None:
        if call.from_user.id != OWNER_ID:
            bot.answer_callback_query(call.id)
            return

        _, chat_id_str, conn_id = call.data.split(":", 2)
        chat_id = int(chat_id_str)

        connection = get_connection(conn_id)
        if not connection or not connection["can_reply"]:
            bot.answer_callback_query(call.id, "Нет активного подключения или нет прав отвечать")
            return

        history = get_conversation_history(conn_id, chat_id)
        last_user_msg = next(
            (r["text"] for r in reversed(history) if r["role"] == "user"), None
        )
        if not last_user_msg:
            bot.answer_callback_query(call.id, "Нет сообщений клиента для ответа")
            return

        bot.answer_callback_query(call.id, "Генерирую ответ...")

        settings = get_settings(OWNER_ID)
        reply = generate_reply(last_user_msg, history, settings.get("business_context"))

        if not reply:
            bot.send_message(call.message.chat.id, "❌ Не удалось сгенерировать ответ. Попробуй позже.")
            return

        try:
            bot.send_message(chat_id, reply, business_connection_id=conn_id)
            save_message(conn_id, chat_id, "assistant", reply)
            mark_not_pending(conn_id, chat_id)
            bot.edit_message_reply_markup(
                call.message.chat.id, call.message.message_id, reply_markup=None
            )
            bot.send_message(
                call.message.chat.id,
                f"✅ <b>Авто-ответ отправлен:</b>\n\n{reply}",
                parse_mode="HTML",
            )
        except Exception as e:
            logging.error("ar_now send failed (chat=%d): %s", chat_id, e)
            bot.send_message(call.message.chat.id, f"❌ Ошибка отправки: {e}")

    @bot.callback_query_handler(func=lambda c: c.data == "cancel")
    def on_cancel(call: CallbackQuery) -> None:
        try:
            bot.edit_message_reply_markup(
                call.message.chat.id, call.message.message_id, reply_markup=None
            )
        except Exception:
            pass
        bot.answer_callback_query(call.id, "Отменено")
