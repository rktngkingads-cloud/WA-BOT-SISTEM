from __future__ import annotations

from typing import Any


def parse_timestamp(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def extract_delivery_statuses(payload: dict[str, Any]) -> list[dict[str, Any]]:
    statuses: list[dict[str, Any]] = []
    for entry in _as_list(payload.get("entry")):
        if not isinstance(entry, dict):
            continue
        for change in _as_list(entry.get("changes")):
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            for item in _as_list(value.get("statuses")):
                if not isinstance(item, dict):
                    continue
                message_id = item.get("id")
                state = item.get("status")
                if not message_id or not state:
                    continue

                errors = _as_list(item.get("errors"))
                error: str | None = None
                if errors and isinstance(errors[0], dict):
                    first = errors[0]
                    error = str(
                        first.get("message")
                        or first.get("title")
                        or first.get("code")
                        or "Unknown delivery error"
                    )

                statuses.append(
                    {
                        "message_id": str(message_id),
                        "status": str(state).strip().casefold(),
                        "recipient_id": str(item.get("recipient_id") or "unknown"),
                        "timestamp": parse_timestamp(item.get("timestamp")),
                        "error": error,
                        "raw": item,
                    }
                )

    return statuses
