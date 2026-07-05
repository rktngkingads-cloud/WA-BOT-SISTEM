from __future__ import annotations

import argparse
import json

from response_config import list_response_rules, select_response


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect local response data")
    parser.add_argument("--message")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        print(json.dumps({"rules": list_response_rules()}, ensure_ascii=False, indent=2))
        return 0

    if not args.message:
        parser.error("Use --message or --list")

    matched, response = select_response(args.message)
    print(
        json.dumps(
            {"matched": matched, "response": response},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
