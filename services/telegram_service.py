import logging

import telebot

from config.settings import BOT_TOKEN
from handlers.business_handler import register_business_handlers
from handlers.callback_handler import register_callback_handlers
from handlers.command_handler import register_command_handlers


def init_bot() -> telebot.TeleBot:
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None, threaded=True, num_threads=4)

    bot.delete_webhook(drop_pending_updates=True)
    logging.info("Webhook removed, starting polling mode")

    register_command_handlers(bot)
    register_business_handlers(bot)
    register_callback_handlers(bot)

    logging.info("Bot initialized, all handlers registered")
    return bot
