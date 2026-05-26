import sqlite3
from typing import Optional

from database.db import get_db

_ALLOWED_SETTINGS = frozenset(
    {"auto_reply", "hours_start", "hours_end", "tz_offset_minutes", "business_context"}
)

_DEFAULTS: dict = {
    "auto_reply": False,
    "hours_start": None,
    "hours_end": None,
    "tz_offset_minutes": 0,
    "business_context": None,
}


def get_settings(owner_id: int) -> dict:
    row = get_db().execute(
        "SELECT * FROM owner_settings WHERE owner_id = ?", (owner_id,)
    ).fetchone()
    if row:
        return dict(row)
    return {"owner_id": owner_id, **_DEFAULTS}


def set_setting(owner_id: int, key: str, value) -> None:
    if key not in _ALLOWED_SETTINGS:
        raise ValueError(f"Unknown setting key: {key!r}")
    db = get_db()
    # key is validated against a whitelist — f-string interpolation is safe here
    db.execute(
        f"""
        INSERT INTO owner_settings (owner_id, {key}, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(owner_id) DO UPDATE SET
            {key}      = excluded.{key},
            updated_at = CURRENT_TIMESTAMP
        """,
        (owner_id, value),
    )
    db.commit()


def upsert_connection(
    connection_id: str,
    owner_id: int,
    owner_chat_id: int,
    can_reply: bool,
    is_active: bool,
) -> None:
    db = get_db()
    db.execute(
        """
        INSERT INTO business_connections
            (connection_id, owner_id, owner_chat_id, can_reply, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(connection_id) DO UPDATE SET
            can_reply     = excluded.can_reply,
            is_active     = excluded.is_active,
            owner_chat_id = excluded.owner_chat_id,
            updated_at    = CURRENT_TIMESTAMP
        """,
        (connection_id, owner_id, owner_chat_id, can_reply, is_active),
    )
    db.commit()


def get_connection(connection_id: str) -> Optional[sqlite3.Row]:
    return get_db().execute(
        "SELECT * FROM business_connections WHERE connection_id = ?",
        (connection_id,),
    ).fetchone()


def get_active_connections(owner_id: int) -> list[sqlite3.Row]:
    return get_db().execute(
        "SELECT * FROM business_connections WHERE owner_id = ? AND is_active = 1",
        (owner_id,),
    ).fetchall()
