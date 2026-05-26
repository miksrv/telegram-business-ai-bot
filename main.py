"""
Telegram Business AI Bot
Handles business_message updates and responds via Groq AI on behalf of the account owner.
"""

import logging
import os
import signal
import sys
import time

from dotenv import load_dotenv

load_dotenv()

_log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _log_level, logging.INFO),
    format="[%(levelname)s] %(name)s: %(message)s",
)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.db import close_db, init_db
from services.telegram_service import init_bot

_ALLOWED_UPDATES = [
    "message",
    "callback_query",
    "business_connection",
    "business_message",
    "edited_business_message",
    "deleted_business_messages",
]


def _shutdown(signum, frame):
    logging.info("Shutting down...")
    close_db()
    sys.exit(0)


signal.signal(signal.SIGINT, _shutdown)
signal.signal(signal.SIGTERM, _shutdown)


if __name__ == "__main__":
    logging.info("Business AI Bot starting...")
    init_db()
    bot = init_bot()

    while True:
        try:
            bot.infinity_polling(
                timeout=60,
                long_polling_timeout=60,
                allowed_updates=_ALLOWED_UPDATES,
            )
        except Exception as e:
            logging.critical("Polling crashed: %s", e)
            time.sleep(10)
