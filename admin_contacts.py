from __future__ import annotations

import argparse
import json
from typing import Any

from contact_store import (
    get_contact,
    init_contact_store,
    list_contacts,
    set_opt_in,
    set_opt_out,
)
from storage import init_database, list_messages
from wa_client import normalize_phone


def output(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def contact_report(phone: str) -> dict[str, Any]:
    contact = get_contact(phone)
    rows = [item for item in list_messages(500) if item.get("phone") == phone]
    incoming = [item for item in rows if item.get("direction") == "incoming"]
    outgoing = [item for item in rows if item.get("direction") == "outgoing"]
    return {
        "found": contact is not None,
        "contact": contact,
        "database_activity": {
            "has_incoming_messages": bool(incoming),
            "incoming_count": len(incoming),
            "outgoing_count": len(outgoing),
            "last_incoming": incoming[0] if incoming else None,
            "last_outgoing": outgoing[0] if outgoing else None,
            "latest_message": rows[0] if rows else None,
        },
        "activity_source": "local webhook and delivery database",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage consent records")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("init", help="Initialize the contact database")

    add = commands.add_parser("add", help="Store an opted-in contact")
    add.add_argument("--phone", required=True)
    add.add_argument("--source", required=True)
    add.add_argument("--note", default="")
    add.add_argument("--consent-at", type=int, default=None)

    remove = commands.add_parser("opt-out", help="Record an opt-out")
    remove.add_argument("--phone", required=True)

    show = commands.add_parser("show", help="Show one contact and stored activity")
    show.add_argument("--phone", required=True)

    listing = commands.add_parser("list", help="List contacts")
    listing.add_argument("--limit", type=int, default=100)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    init_contact_store()
    init_database()

    if args.command == "init":
        output({"initialized": True})
        return 0

    if args.command == "add":
        phone = normalize_phone(args.phone)
        set_opt_in(
            phone,
            source=args.source,
            note=args.note,
            consent_at=args.consent_at,
        )
        output({"saved": True, "contact": get_contact(phone)})
        return 0

    if args.command == "opt-out":
        phone = normalize_phone(args.phone)
        set_opt_out(phone)
        output({"saved": True, "contact": get_contact(phone)})
        return 0

    if args.command == "show":
        phone = normalize_phone(args.phone)
        output(contact_report(phone))
        return 0

    output({"items": list_contacts(args.limit)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
