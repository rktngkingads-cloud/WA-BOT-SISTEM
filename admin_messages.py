from __future__ import annotations

import argparse
import json
from typing import Any

from env_loader import load_local_env

load_local_env()

from storage import init_database, list_messages, status_summary


def output(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read stored message status data")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("summary", help="Show stored status totals")

    listing = commands.add_parser("list", help="List recent stored messages")
    listing.add_argument("--limit", type=int, default=100)

    message = commands.add_parser("show", help="Show one stored message")
    message.add_argument("--message-id", required=True)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    init_database()

    if args.command == "summary":
        output({"status_summary": status_summary()})
        return 0

    items = list_messages(args.limit if args.command == "list" else 500)
    if args.command == "list":
        output({"items": items})
        return 0

    item = next(
        (row for row in items if row.get("message_id") == args.message_id),
        None,
    )
    output(item or {"found": False, "message_id": args.message_id})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
