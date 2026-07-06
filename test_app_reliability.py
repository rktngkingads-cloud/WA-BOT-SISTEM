from __future__ import annotations

from app import extract_incoming_texts, is_valid_signature


def test_malformed_incoming_nodes_are_ignored():
    payload = {
        "entry": [
            None,
            {
                "changes": [
                    None,
                    {
                        "value": {
                            "messages": [
                                None,
                                {
                                    "id": "wamid.test",
                                    "from": "+60 12-345 6789",
                                    "type": "text",
                                    "text": {"body": "hello"},
                                },
                            ]
                        }
                    },
                ]
            },
        ]
    }

    messages = extract_incoming_texts(payload)
    assert len(messages) == 1
    assert messages[0]["sender"] == "60123456789"
    assert messages[0]["body"] == "hello"


def test_signature_without_secret_is_offline_only(monkeypatch):
    monkeypatch.delenv("WA_APP_SECRET", raising=False)

    monkeypatch.setenv("WA_MODE", "offline")
    assert is_valid_signature(b"{}", None) is True

    monkeypatch.setenv("WA_MODE", "meta")
    assert is_valid_signature(b"{}", None) is False
