import sqlite3
from datetime import datetime
from typing import Optional

from database.db import get_db


def upsert_conversation(
    connection_id: str,
    chat_id: int,
    user_id: int,
    user_name: str,
    username: Optional[str],
    pending: bool = True,
) -> None:
    db = get_db()
    db.execute(
        """
        INSERT INTO conversations
            (connection_id, chat_id, user_id, user_name, username,
             last_message_at, message_count, is_pending)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1, ?)
        ON CONFLICT(connection_id, chat_id) DO UPDATE SET
            user_name       = excluded.user_name,
            username        = excluded.username,
            last_message_at = CURRENT_TIMESTAMP,
            message_count   = message_count + 1,
            is_pending      = ?
        """,
        (connection_id, chat_id, user_id, user_name, username, pending, pending),
    )
    db.commit()


def mark_not_pending(connection_id: str, chat_id: int) -> None:
    db = get_db()
    db.execute(
        "UPDATE conversations SET is_pending = 0 WHERE connection_id = ? AND chat_id = ?",
        (connection_id, chat_id),
    )
    db.commit()


def get_all_pending() -> list[sqlite3.Row]:
    return get_db().execute(
        """
        SELECT * FROM conversations
        WHERE is_pending = 1
        ORDER BY last_message_at DESC
        """
    ).fetchall()


def save_message(connection_id: str, chat_id: int, role: str, text: str) -> None:
    db = get_db()
    db.execute(
        "INSERT INTO messages (connection_id, chat_id, role, text) VALUES (?, ?, ?, ?)",
        (connection_id, chat_id, role, text),
    )
    db.commit()


def get_conversation_history(
    connection_id: str, chat_id: int, limit: int = 15
) -> list[sqlite3.Row]:
    rows = get_db().execute(
        """
        SELECT role, text FROM messages
        WHERE connection_id = ? AND chat_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (connection_id, chat_id, limit),
    ).fetchall()
    return list(reversed(rows))


def get_message_count(connection_id: str, chat_id: int) -> int:
    row = get_db().execute(
        "SELECT message_count FROM conversations WHERE connection_id = ? AND chat_id = ?",
        (connection_id, chat_id),
    ).fetchone()
    return row["message_count"] if row else 0


def get_today_stats(connection_id: str) -> dict:
    db = get_db()
    today = datetime.utcnow().strftime("%Y-%m-%d")

    received = db.execute(
        "SELECT COUNT(*) FROM messages WHERE connection_id = ? AND role = 'user' AND date(created_at) = ?",
        (connection_id, today),
    ).fetchone()[0]

    sent = db.execute(
        "SELECT COUNT(*) FROM messages WHERE connection_id = ? AND role = 'assistant' AND date(created_at) = ?",
        (connection_id, today),
    ).fetchone()[0]

    pending = db.execute(
        "SELECT COUNT(*) FROM conversations WHERE connection_id = ? AND is_pending = 1",
        (connection_id,),
    ).fetchone()[0]

    return {"received": received, "sent": sent, "pending": pending}
