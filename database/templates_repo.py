import sqlite3
from typing import Optional

from database.db import get_db


def add_template(owner_id: int, name: str, text: str) -> bool:
    try:
        db = get_db()
        db.execute(
            "INSERT INTO templates (owner_id, name, text) VALUES (?, ?, ?)",
            (owner_id, name, text),
        )
        db.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def upsert_template(owner_id: int, name: str, text: str) -> None:
    db = get_db()
    db.execute(
        """
        INSERT INTO templates (owner_id, name, text)
        VALUES (?, ?, ?)
        ON CONFLICT(owner_id, name) DO UPDATE SET text = excluded.text
        """,
        (owner_id, name, text),
    )
    db.commit()


def delete_template(owner_id: int, name: str) -> bool:
    db = get_db()
    cursor = db.execute(
        "DELETE FROM templates WHERE owner_id = ? AND name = ?",
        (owner_id, name),
    )
    db.commit()
    return cursor.rowcount > 0


def get_template_by_id(template_id: int) -> Optional[sqlite3.Row]:
    return get_db().execute(
        "SELECT * FROM templates WHERE id = ?", (template_id,)
    ).fetchone()


def list_templates(owner_id: int) -> list[sqlite3.Row]:
    return get_db().execute(
        "SELECT * FROM templates WHERE owner_id = ? ORDER BY name",
        (owner_id,),
    ).fetchall()
