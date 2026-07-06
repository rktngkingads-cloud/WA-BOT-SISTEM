from __future__ import annotations

from pathlib import Path

from storage import get_message, init_database, save_message


def test_status_does_not_regress_and_body_is_backfilled(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("WA_DB_PATH", str(tmp_path / "messages.db"))
    init_database()

    assert save_message(
        message_id="wamid.1",
        direction="outgoing",
        phone="unknown",
        body="",
        status="delivered",
    ) == "delivered"

    assert save_message(
        message_id="wamid.1",
        direction="outgoing",
        phone="60123456789",
        body="hello",
        status="accepted",
    ) == "delivered"

    message = get_message("wamid.1")
    assert message is not None
    assert message["phone"] == "60123456789"
    assert message["body"] == "hello"
    assert message["status"] == "delivered"

    assert save_message(
        message_id="wamid.1",
        direction="outgoing",
        phone="60123456789",
        body="",
        status="read",
    ) == "read"
    assert save_message(
        message_id="wamid.1",
        direction="outgoing",
        phone="60123456789",
        body="",
        status="sent",
    ) == "read"
    assert save_message(
        message_id="wamid.1",
        direction="outgoing",
        phone="60123456789",
        body="",
        status="failed",
        error="late failure",
    ) == "read"
