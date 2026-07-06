from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from contact_store import get_contact, init_contact_store, set_opt_in
from queue_store import enqueue_message, init_queue_store
from storage import init_database
from wa_client import normalize_phone

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class BatchRow:
    line_number: int
    contact_name: str
    phone: str
    message: str
    consent: bool
    consent_source: str
    consent_note: str


@dataclass(frozen=True)
class PlannedItem:
    row: BatchRow
    delay_seconds: int
    needs_opt_in: bool


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


def parse_bool(value: object) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "y", "on", "opt-in"}


def read_batch_csv(path: Path, common_message: str = "") -> list[BatchRow]:
    if not path.is_file():
        raise FileNotFoundError(f"Batch file was not found: {path}")

    rows: list[BatchRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"phone", "contact_name", "consent", "consent_source"}
        headers = {str(name or "").strip() for name in (reader.fieldnames or [])}
        missing = sorted(required - headers)
        if missing:
            raise ValueError(f"Missing CSV columns: {', '.join(missing)}")

        for line_number, raw in enumerate(reader, start=2):
            phone_raw = str(raw.get("phone") or "").strip()
            if not phone_raw:
                continue
            phone = normalize_phone(phone_raw)
            message = str(raw.get("message") or common_message).strip()
            if not message:
                raise ValueError(f"Line {line_number}: message is empty")

            rows.append(
                BatchRow(
                    line_number=line_number,
                    contact_name=str(raw.get("contact_name") or "").strip(),
                    phone=phone,
                    message=message,
                    consent=parse_bool(raw.get("consent")),
                    consent_source=str(raw.get("consent_source") or "").strip(),
                    consent_note=str(raw.get("consent_note") or "").strip(),
                )
            )
    return rows


def build_plan(
    rows: list[BatchRow],
    *,
    initial_delay_seconds: int,
    gap_seconds: int,
    maximum_contacts: int,
) -> tuple[list[PlannedItem], list[str]]:
    if maximum_contacts < 1:
        raise ValueError("maximum_contacts must be at least 1")
    if len(rows) > maximum_contacts:
        raise ValueError(
            f"Batch contains {len(rows)} contacts; configured maximum is {maximum_contacts}"
        )

    initial_delay = max(1, int(initial_delay_seconds))
    gap = max(1, int(gap_seconds))
    seen: set[str] = set()
    plan: list[PlannedItem] = []
    errors: list[str] = []

    for row in rows:
        if row.phone in seen:
            errors.append(f"Line {row.line_number}: duplicate phone {row.phone}")
            continue
        seen.add(row.phone)

        contact = get_contact(row.phone)
        opted_in = bool(contact and int(contact.get("opted_in") or 0) == 1)
        needs_opt_in = not opted_in

        if needs_opt_in and not row.consent:
            errors.append(
                f"Line {row.line_number}: {row.phone} is not opted in and consent is not yes"
            )
            continue
        if needs_opt_in and not row.consent_source:
            errors.append(
                f"Line {row.line_number}: consent_source is required for a new opt-in"
            )
            continue

        delay = initial_delay + len(plan) * gap
        plan.append(PlannedItem(row=row, delay_seconds=delay, needs_opt_in=needs_opt_in))

    return plan, errors


def queue_plan(plan: list[PlannedItem]) -> tuple[list[int], list[str]]:
    queued_ids: list[int] = []
    errors: list[str] = []

    for item in plan:
        row = item.row
        try:
            if item.needs_opt_in:
                set_opt_in(
                    row.phone,
                    source=row.consent_source,
                    note=row.consent_note,
                    display_name=row.contact_name,
                )
            item_id = enqueue_message(row.phone, row.message, item.delay_seconds)
            queued_ids.append(item_id)
        except (ValueError, RuntimeError) as exc:
            errors.append(f"Line {row.line_number}: {row.phone}: {exc}")

    return queued_ids, errors


def prompt_value(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Queue one-to-one WhatsApp messages from a consented CSV contact list."
    )
    parser.add_argument("--file", default="batch_contacts.csv", help="CSV batch file")
    parser.add_argument("--message", default="", help="Common message when CSV message is empty")
    parser.add_argument("--initial-delay", type=int, default=None)
    parser.add_argument("--gap", type=int, default=None, help="Delay between each contact")
    parser.add_argument("--yes", action="store_true", help="Queue without interactive confirmation")
    parser.add_argument("--dry-run", action="store_true", help="Validate and preview only")
    args = parser.parse_args(argv)

    init_database()
    init_contact_store()
    init_queue_store()

    minimum = max(1, env_int("WA_QUEUE_MIN_DELAY_SECONDS", 15))
    configured_gap = max(minimum, env_int("WA_BATCH_GAP_SECONDS", 20))
    configured_initial = max(minimum, env_int("WA_BATCH_INITIAL_DELAY_SECONDS", 30))
    maximum = max(1, env_int("WA_BATCH_MAX_CONTACTS", 50))

    file_path = Path(args.file)
    if not file_path.is_absolute():
        file_path = ROOT / file_path

    common_message = args.message.strip()
    if not common_message and sys.stdin.isatty():
        common_message = prompt_value("Common message; CSV row message may override it")

    initial_delay = max(minimum, args.initial_delay or configured_initial)
    gap = max(minimum, args.gap or configured_gap)

    try:
        rows = read_batch_csv(file_path, common_message)
        plan, validation_errors = build_plan(
            rows,
            initial_delay_seconds=initial_delay,
            gap_seconds=gap,
            maximum_contacts=maximum,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print("\nONE-TO-ONE BATCH QUEUE PREVIEW")
    print(f"File           : {file_path}")
    print(f"Valid contacts : {len(plan)}")
    print(f"Rejected rows  : {len(validation_errors)}")
    print(f"Initial delay  : {initial_delay} seconds")
    print(f"Contact gap    : {gap} seconds")
    if plan:
        print(f"Estimated span : {plan[-1].delay_seconds} seconds until final item is due")

    for item in plan[:20]:
        name = item.row.contact_name or "-"
        state = "NEW OPT-IN" if item.needs_opt_in else "OPTED-IN"
        print(
            f"  line {item.row.line_number:<4} {name[:20]:<20} "
            f"{item.row.phone:<16} WAIT {item.delay_seconds:>5}s {state}"
        )
    if len(plan) > 20:
        print(f"  ... and {len(plan) - 20} more")

    if validation_errors:
        print("\nREJECTED")
        for error in validation_errors:
            print(f"  - {error}")

    if not plan:
        print("No valid contacts to queue.")
        return 1
    if args.dry_run:
        print("Dry run completed; no messages were queued.")
        return 0

    if not args.yes:
        confirmation = input("\nType QUEUE to add these one-to-one messages: ").strip()
        if confirmation != "QUEUE":
            print("Cancelled; no messages were queued.")
            return 0

    queued_ids, queue_errors = queue_plan(plan)
    print(f"\nQueued successfully: {len(queued_ids)}")
    if queue_errors:
        print(f"Queue errors       : {len(queue_errors)}")
        for error in queue_errors:
            print(f"  - {error}")

    print("Open wa_monitor.py or run_wa_bot.bat to watch each contact countdown.")
    return 0 if queued_ids else 1


if __name__ == "__main__":
    raise SystemExit(main())
