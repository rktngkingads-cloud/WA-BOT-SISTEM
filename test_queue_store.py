from __future__ import annotations

from pathlib import Path

import pytest

from queue_store import (
    cancel_pending,
    claim_due_message,
    enqueue_message,
    init_queue_store,
    list_queue,
    mark_queue_item,
    pending_by_phone,
    queue_summary,
)


def test_queue_countdown_data_and_one_pending(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("WA_DB_PATH", str(tmp_path / "queue.db"))
    init_queue_store()

    item_id = enqueue_message("60123456789", "hello", 30)
    pending = pending_by_phone()
    assert pending["60123456789"]["id"] == item_id
    assert pending["60123456789"]["status"] == "queued"
    assert pending["60123456789"]["scheduled_at"] > pending["60123456789"]["created_at"]

    with pytest.raises(ValueError, match="pending"):
        enqueue_message("60123456789", "second", 30)

    assert queue_summary()["queued"] == 1


def test_claim_send_and_cancel(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("WA_DB_PATH", str(tmp_path / "queue.db"))
    init_queue_store()

    first_id = enqueue_message("60111111111", "first", 1)
    claimed = claim_due_message(now=10**10)
    assert claimed is not None
    assert claimed["id"] == first_id
    assert claimed["status"] == "sending"

    mark_queue_item(first_id, "sent", message_id="offline.test")
    assert list_queue(1)[0]["status"] == "sent"

    enqueue_message("60122222222", "second", 20)
    assert cancel_pending("60122222222") == 1
    latest = list_queue(1)[0]
    assert latest["status"] == "cancelled"
