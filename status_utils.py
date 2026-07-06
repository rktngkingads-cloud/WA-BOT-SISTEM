from __future__ import annotations

from typing import Final

STATUS_RANK: Final[dict[str, int]] = {
    "received": 10,
    "accepted": 10,
    "sent": 20,
    "failed": 25,
    "delivered": 30,
    "read": 40,
    "simulated": 50,
}

TERMINAL_SUCCESS: Final[set[str]] = {"read", "simulated"}


def normalize_status(value: object, default: str = "unknown") -> str:
    text = str(value or "").strip().casefold()
    return text or default


def choose_status(current: object, incoming: object) -> str:
    old = normalize_status(current, "")
    new = normalize_status(incoming, "")
    if not new:
        return old or "unknown"
    if not old:
        return new
    if old == new:
        return old
    if old in TERMINAL_SUCCESS:
        return old
    if old == "delivered" and new == "failed":
        return old
    if old == "failed":
        return old

    old_rank = STATUS_RANK.get(old)
    new_rank = STATUS_RANK.get(new)
    if new_rank is None:
        return old
    if old_rank is None or new_rank >= old_rank:
        return new
    return old
