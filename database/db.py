import logging
import os
import sqlite3

from config.settings import DB_PATH

_conn: sqlite3.Connection | None = None


def get_db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn


def init_db() -> None:
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS business_connections (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            connection_id   TEXT    UNIQUE NOT NULL,
            owner_id        INTEGER NOT NULL,
            owner_chat_id   INTEGER,
            can_reply       BOOLEAN DEFAULT 1,
            is_active       BOOLEAN DEFAULT 1,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            connection_id   TEXT    NOT NULL,
            chat_id         INTEGER NOT NULL,
            user_id         INTEGER,
            user_name       TEXT,
            username        TEXT,
            last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            message_count   INTEGER DEFAULT 0,
            is_pending      BOOLEAN DEFAULT 0,
            UNIQUE(connection_id, chat_id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            connection_id   TEXT    NOT NULL,
            chat_id         INTEGER NOT NULL,
            role            TEXT    NOT NULL,
            text            TEXT    NOT NULL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_messages_chat
            ON messages(connection_id, chat_id, created_at);

        CREATE TABLE IF NOT EXISTS templates (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id    INTEGER NOT NULL,
            name        TEXT    NOT NULL,
            text        TEXT    NOT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(owner_id, name)
        );

        CREATE TABLE IF NOT EXISTS contact_styles (
            chat_id         INTEGER PRIMARY KEY,
            connection_id   TEXT    NOT NULL,
            style_summary   TEXT    NOT NULL,
            msg_count       INTEGER DEFAULT 0,
            analyzed_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS owner_settings (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id            INTEGER UNIQUE NOT NULL,
            auto_reply          BOOLEAN DEFAULT 0,
            hours_start         TEXT    DEFAULT NULL,
            hours_end           TEXT    DEFAULT NULL,
            tz_offset_minutes   INTEGER DEFAULT 0,
            business_context    TEXT    DEFAULT NULL,
            updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    db.commit()
    logging.info("Database initialized: %s", DB_PATH)


def close_db() -> None:
    global _conn
    if _conn:
        _conn.close()
        _conn = None
