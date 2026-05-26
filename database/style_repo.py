import sqlite3
from typing import Optional

from database.db import get_db


def get_contact_style(chat_id: int) -> Optional[sqlite3.Row]:
    return get_db().execute(
        "SELECT * FROM contact_styles WHERE chat_id = ?", (chat_id,)
    ).fetchone()


def save_contact_style(
    chat_id: int, connection_id: str, style_summary: str, msg_count: int
) -> None:
    db = get_db()
    db.execute(
        """
        INSERT INTO contact_styles (chat_id, connection_id, style_summary, msg_count, analyzed_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(chat_id) DO UPDATE SET
            style_summary = excluded.style_summary,
            msg_count     = excluded.msg_count,
            analyzed_at   = CURRENT_TIMESTAMP
        """,
        (chat_id, connection_id, style_summary, msg_count),
    )
    db.commit()
