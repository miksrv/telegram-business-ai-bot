import logging
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import GROQ_API_KEY, MAX_INPUT_CHARS, MAX_REPLY_TOKENS, MODEL_FAST, MODEL_TEXT
from core.prompts import get_business_reply_prompt, get_classification_prompt

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json",
}

_session = requests.Session()
_session.mount(
    "https://",
    HTTPAdapter(
        max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    ),
)

_VALID_CLASSIFICATIONS = frozenset(
    {"inquiry", "order", "complaint", "spam", "greeting", "other"}
)


def _call_groq(model: str, messages: list, max_tokens: int, temperature: float) -> str | None:
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    for attempt in range(3):
        try:
            r = _session.post(_GROQ_URL, headers=_HEADERS, json=payload, timeout=(5, 30))
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except (requests.ConnectionError, requests.Timeout) as e:
            logging.warning("Groq retry %d/3: %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(2**attempt)
        except Exception as e:
            logging.error("Groq API error: %s", e)
            return None
    return None


def generate_reply(
    text: str,
    history: list,
    business_context: str | None,
) -> str | None:
    text = text[:MAX_INPUT_CHARS]
    system = get_business_reply_prompt(business_context)

    messages = [{"role": "system", "content": system}]

    for row in history[-15:]:
        # Both owner manual replies and bot auto-replies map to "assistant" role
        groq_role = "assistant" if row["role"] in ("assistant", "owner") else "user"
        messages.append({"role": groq_role, "content": row["text"]})

    # Ensure the latest message is the current customer text
    if not messages or messages[-1].get("role") != "user" or messages[-1].get("content") != text:
        messages.append({"role": "user", "content": text})

    return _call_groq(MODEL_TEXT, messages, max_tokens=MAX_REPLY_TOKENS, temperature=0.75)


def classify_message(text: str) -> str:
    prompt = get_classification_prompt(text[:500])
    result = _call_groq(
        MODEL_FAST,
        [{"role": "user", "content": prompt}],
        max_tokens=10,
        temperature=0.1,
    )
    if result:
        label = result.lower().strip().rstrip(".")
        if label in _VALID_CLASSIFICATIONS:
            return label
    return "other"
