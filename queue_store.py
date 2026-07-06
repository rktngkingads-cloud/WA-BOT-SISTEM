from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import Any

QUEUE_STATES = {"queued", "sending", "sent", "failed", "cancelled", "blocked"}


def database_path() -> Path:
    path = Path(os.getenv("WA_DB_PATH", "data/wa-system.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(database_path(), timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def init_queue_store() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS outbound_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT NOT NULL,
                body TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued'
                    CHECK(status IN ('queued', 'sending', 'sent', 'failed', 'cancelled', 'blocked')),
                scheduled_at INTEGER NOT NULL,
                message_id TEXT,
                error TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                sent_at INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_outbound_queue_due
                ON outbound_queue(status, scheduled_at, id);

            CREATE INDEX IF NOT EXISTS idx_outbound_queue_phone
                ON outbound_queue(phone, updated_at DESC);
            """
        )


def enqueue_message(phone: str, body: str, delay_seconds: int) -> int:
    text = str(body).strip()
    if not text:
        raise ValueError("Message cannot be empty")

    delay = max(1, int(delay_seconds))
    now = int(time.time())
    scheduled_at = now + delay

    with connect() as connection:
        existing = connection.execute(
            """
            SELECT id FROM outbound_queue
            WHERE phone = ? AND status IN ('queued', 'sending')
            ORDER BY id DESC LIMIT 1
            """,
            (phone,),
        ).fetchone()
        if existing:
            raise ValueError("This contact already has a pending message")

        cursor = connection.execute(
            """
            INSERT INTO outbound_queue(
                phone, body, status, scheduled_at, created_at, updated_at
            ) VALUES (?, ?, 'queued', ?, ?, ?)
            """,
            (phone, text, scheduled_at, now, now),
        )
        return int(cursor.lastrowid)


def claim_due_message(now: int | None = None) -> dict[str, Any] | None:
    current = int(time.time()) if now is None else int(now)
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            """
            SELECT id, phone, body, status, scheduled_at, message_id, error,
                   created_at, updated_at, sent_at
            FROM outbound_queue
            WHERE status = 'queued' AND scheduled_at <= ?
            ORDER BY scheduled_at ASC, id ASC
            LIMIT 1
            """,
            (current,),
        ).fetchone()
        if row is None:
            connection.commit()
            return None

        cursor = connection.execute(
            """
            UPDATE outbound_queue
            SET status = 'sending', updated_at = ?
            WHERE id = ? AND status = 'queued'
            """,
            (current, int(row["id"])),
        )
        connection.commit()
        if cursor.rowcount != 1:
            return None

    result = dict(row)
    result["status"] = "sending"
    result["updated_at"] = current
    return result


def mark_queue_item(
    item_id: int,
    status: str,
    *,
    message_id: str | None = None,
    error: str | None = None,
) -> None:
    if status not in QUEUE_STATES:
        raise ValueError(f"Invalid queue status: {status}")
    now = int(time.time())
    sent_at = now if status == "sent" else None
    with connect() as connection:
        connection.execute(
            """
            UPDATE outbound_queue
            SET status = ?, message_id = COALESCE(?, message_id), error = ?,
                sent_at = COALESCE(?, sent_at), updated_at = ?
            WHERE id = ?
            """,
            (status, message_id, error, sent_at, now, int(item_id)),
        )


def requeue_sending_items() -> int:
    """Recover items left in SENDING after an unexpected service stop."""
    now = int(time.time())
    with connect() as connection:
        cursor = connection.execute(
            """
            UPDATE outbound_queue
            SET status = 'queued', error = 'Recovered after service restart', updated_at = ?
            WHERE status = 'sending'
            """,
            (now,),
        )
        return int(cursor.rowcount)


def cancel_pending(phone: str) -> int:
    now = int(time.time())
    with connect() as connection:
        cursor = connection.execute(
            """
            UPDATE outbound_queue
            SET status = 'cancelled', error = 'Cancelled from CMD monitor', updated_at = ?
            WHERE phone = ? AND status = 'queued'
            """,
            (now, phone),
        )
        return int(cursor.rowcount)


def list_queue(limit: int = 100, statuses: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    with connect() as connection:
        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            rows = connection.execute(
                f"""
                SELECT id, phone, body, status, scheduled_at, message_id, error,
                       created_at, updated_at, sent_at
                FROM outbound_queue
                WHERE status IN ({placeholders})
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (*statuses, limit),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT id, phone, body, status, scheduled_at, message_id, error,
                       created_at, updated_at, sent_at
                FROM outbound_queue
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [dict(row) for row in rows]


def pending_by_phone() -> dict[str, dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT q.id, q.phone, q.body, q.status, q.scheduled_at, q.message_id,
                   q.error, q.created_at, q.updated_at, q.sent_at
            FROM outbound_queue q
            JOIN (
                SELECT phone, MAX(id) AS max_id
                FROM outbound_queue
                WHERE status IN ('queued', 'sending')
                GROUP BY phone
            ) latest ON latest.max_id = q.id
            """
        ).fetchall()
    return {str(row["phone"]): dict(row) for row in rows}


def queue_summary() -> dict[str, int]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT status, COUNT(*) AS total FROM outbound_queue GROUP BY status"
        ).fetchall()
    return {str(row["status"]): int(row["total"]) for row in rows}
