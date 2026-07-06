from __future__ import annotations

import asyncio
from pathlib import Path

from contact_store import init_contact_store, set_opt_in, set_opt_out
from wa_client import allowed_recipients, normalize_phone, send_allowed_reply


def test_normalize_phone():
    assert normalize_phone("+60 12-345 6789") == "60123456789"


def test_database_opt_in_and_opt_out_override(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("WA_DB_PATH", str(tmp_path / "contacts.db"))
    monkeypatch.setenv("WA_ALLOWED_RECIPIENTS", "60111111111")
    init_contact_store()

    set_opt_in("60122222222", source="test")
    assert allowed_recipients() == {"60111111111", "60122222222"}

    set_opt_out("60111111111")
    assert allowed_recipients() == {"60122222222"}


def test_offline_send(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("WA_DB_PATH", str(tmp_path / "contacts.db"))
    monkeypatch.setenv("WA_ALLOWED_RECIPIENTS", "60111111111")
    monkeypatch.setenv("WA_MODE", "offline")
    init_contact_store()

    result = asyncio.run(send_allowed_reply("60111111111", "test"))
    assert result["mode"] == "offline"
    assert result["messages"][0]["id"].startswith("offline.")
