from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from db_utils import connect, database_path, initialize_pragmas
from status_utils import choose_status


def init_database() -> None:
    with connect() as connection:
        initialize_pragmas(connection)
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                direction TEXT NOT NULL CHECK(direction IN ('incoming', 'outgoing')),
                phone TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                event_timestamp INTEGER,
                error TEXT,
                raw_json TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_messages_phone_time
                ON messages(phone, updated_at DESC);

            CREATE INDEX IF NOT EXISTS idx_messages_status
                ON messages(status, updated_at DESC);
            """
        )


def message_exists(message_id: str) -> bool:
    with connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM messages WHERE message_id = ? LIMIT 1",
            (message_id,),
        ).fetchone()
    return row is not None


def get_message(message_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT message_id, direction, phone, body, status,
                   event_timestamp, error, raw_json, created_at, updated_at
            FROM messages WHERE message_id = ?
            """,
            (message_id,),
        ).fetchone()
    return dict(row) if row else None


def save_message(
    *,
    message_id: str,
    direction: str,
    phone: str,
    body: str,
    status: str,
    event_timestamp: int | None = None,
    error: str | None = None,
    raw: dict[str, Any] | None = None,
) -> str:
    if direction not in {"incoming", "outgoing"}:
        raise ValueError("direction must be incoming or outgoing")

    now = int(time.time())
    raw_json = json.dumps(raw, ensure_ascii=False, separators=(",", ":")) if raw else None
    clean_body = str(body or "")
    clean_phone = str(phone or "unknown")
    clean_status = str(status or "unknown").strip().casefold() or "unknown"

    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT direction, phone, body, status, event_timestamp, error, raw_json, created_at "
            "FROM messages WHERE message_id = ?",
            (message_id,),
        ).fetchone()

        if existing is None:
            effective_status = clean_status
            connection.execute(
                """
                INSERT INTO messages (
                    message_id, direction, phone, body, status,
                    event_timestamp, error, raw_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    direction,
                    clean_phone,
                    clean_body,
                    effective_status,
                    event_timestamp,
                    error,
                    raw_json,
                    now,
                    now,
                ),
            )
        else:
            effective_status = choose_status(existing["status"], clean_status)
            effective_direction = (
                direction
                if existing["body"] == "" and clean_body and direction == "outgoing"
                else str(existing["direction"])
            )
            effective_phone = (
                clean_phone
                if str(existing["phone"] or "") in {"", "unknown"} and clean_phone != "unknown"
                else str(existing["phone"])
            )
            effective_body = clean_body if clean_body else str(existing["body"] or "")
            effective_event_timestamp = (
                event_timestamp if event_timestamp is not None else existing["event_timestamp"]
            )
            effective_error = error if effective_status == clean_status else existing["error"]
            effective_raw = raw_json or existing["raw_json"]

            connection.execute(
                """
                UPDATE messages
                SET direction = ?, phone = ?, body = ?, status = ?,
                    event_timestamp = ?, error = ?, raw_json = ?, updated_at = ?
                WHERE message_id = ?
                """,
                (
                    effective_direction,
                    effective_phone,
                    effective_body,
                    effective_status,
                    effective_event_timestamp,
                    effective_error,
                    effective_raw,
                    now,
                    message_id,
                ),
            )
        connection.commit()
    return effective_status


def list_messages(limit: int = 100) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT message_id, direction, phone, body, status,
                   event_timestamp, error, created_at, updated_at
            FROM messages
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def status_summary() -> dict[str, int]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT status, COUNT(*) AS total FROM messages GROUP BY status"
        ).fetchall()
    return {str(row["status"]): int(row["total"]) for row in rows}


def database_health() -> dict[str, Any]:
    try:
        with connect() as connection:
            integrity = connection.execute("PRAGMA quick_check").fetchone()
            journal = connection.execute("PRAGMA journal_mode").fetchone()
        return {
            "ok": bool(integrity and str(integrity[0]).casefold() == "ok"),
            "integrity": str(integrity[0]) if integrity else "unknown",
            "journal_mode": str(journal[0]) if journal else "unknown",
            "path": str(database_path()),
        }
    except sqlite3.Error as exc:
        return {"ok": False, "error": str(exc), "path": str(database_path())}
