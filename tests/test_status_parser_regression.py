from __future__ import annotations

from status_parser import extract_delivery_statuses


def test_malformed_status_nodes_are_ignored():
    payload = {
        "entry": [
            None,
            {
                "changes": [
                    None,
                    {"value": {"statuses": [None, {"id": "wamid.1", "status": "read"}]}},
                ]
            },
        ]
    }

    statuses = extract_delivery_statuses(payload)
    assert len(statuses) == 1
    assert statuses[0]["message_id"] == "wamid.1"
    assert statuses[0]["status"] == "read"
