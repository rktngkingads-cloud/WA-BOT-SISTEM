import json
from pathlib import Path

from admin_contacts import contact_report
from contact_store import init_contact_store, set_opt_in
from response_config import select_response
from storage import init_database, save_message


def test_contact_report_uses_local_message_data(tmp_path: Path, monkeypatch):
    database = tmp_path / "admin.db"
    monkeypatch.setenv("WA_DB_PATH", str(database))
    init_contact_store()
    init_database()

    set_opt_in("60123456789", source="test")
    save_message(
        message_id="wamid.incoming",
        direction="incoming",
        phone="60123456789",
        body="hello",
        status="received",
    )
    save_message(
        message_id="wamid.outgoing",
        direction="outgoing",
        phone="60123456789",
        body="reply",
        status="delivered",
    )

    result = contact_report("60123456789")
    assert result["found"] is True
    assert result["database_activity"]["has_incoming_messages"] is True
    assert result["database_activity"]["incoming_count"] == 1
    assert result["database_activity"]["outgoing_count"] == 1


def test_response_selection_from_json(tmp_path: Path, monkeypatch):
    response_file = tmp_path / "responses.json"
    response_file.write_text(
        json.dumps(
            {
                "default": "default reply",
                "rules": [
                    {"keywords": ["hello"], "response": "matched reply"}
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("WA_RESPONSE_DATA_PATH", str(response_file))

    assert select_response("hello there") == ("rule:0", "matched reply")
    assert select_response("unknown") == ("default", "default reply")
