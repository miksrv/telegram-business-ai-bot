import os

from dotenv import load_dotenv

load_dotenv()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name!r} is not set")
    return value


BOT_TOKEN = require_env("BOT_TOKEN")
GROQ_API_KEY = require_env("GROQ_API_KEY")
OWNER_ID = int(require_env("OWNER_ID"))

MODEL_TEXT = "llama-3.3-70b-versatile"
MODEL_FAST = "llama-3.1-8b-instant"

MAX_HISTORY_MESSAGES = 15
MAX_INPUT_CHARS = 2000
MAX_REPLY_TOKENS = 400
MAX_CONTEXT_CHARS = 3000

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "business_bot.db")
