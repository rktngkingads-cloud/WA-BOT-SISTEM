from __future__ import annotations

import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from contact_store import (
    get_contact,
    init_contact_store,
    list_contacts,
    replies_today,
    set_opt_in,
    set_opt_out,
    update_display_name,
)
from queue_store import (
    cancel_pending,
    enqueue_message,
    init_queue_store,
    list_queue,
    queue_summary,
)
from storage import init_database, list_messages, status_summary
from wa_client import allowed_recipients, mode, normalize_phone

load_dotenv(Path(__file__).resolve().with_name(".env"))

RESET = "\033[0m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
DIM = "\033[2m"


def enable_terminal() -> None:
    if os.name == "nt":
        os.system("")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass


def clear_screen() -> None:
    if os.name == "nt":
        os.system("cls")
    elif os.getenv("TERM"):
        os.system("clear")
    else:
        print("\033[2J\033[H", end="")


def color(text: str, value: str) -> str:
    if os.getenv("NO_COLOR"):
        return text
    return f"{value}{text}{RESET}"


def clip(value: Any, width: int) -> str:
    text = str(value or "").replace("\n", " ")
    if width <= 1:
        return text[:width]
    return text if len(text) <= width else text[: width - 1] + "…"


def human_time(timestamp: int | None) -> str:
    if not timestamp:
        return "-"
    try:
        return datetime.fromtimestamp(int(timestamp), tz=timezone.utc).astimezone().strftime("%H:%M:%S")
    except (OSError, TypeError, ValueError):
        return "-"


def day_key() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def server_status() -> tuple[str, dict[str, Any]]:
    url = os.getenv("WA_MONITOR_HEALTH_URL", "http://127.0.0.1:8000/health").strip()
    try:
        with urllib.request.urlopen(url, timeout=0.7) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return "RUNNING", payload if isinstance(payload, dict) else {}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return "OFFLINE", {}


def recent_activity_by_phone(messages: list[dict[str, Any]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in messages:
        phone = str(item.get("phone") or "")
        timestamp = int(item.get("updated_at") or item.get("created_at") or 0)
        if phone and timestamp > result.get(phone, 0):
            result[phone] = timestamp
    return result


def estimated_pending_by_phone(
    queue_items: list[dict[str, Any]],
    *,
    worker_enabled: bool,
    global_gap_seconds: float,
    global_wait_seconds: float,
) -> dict[str, dict[str, Any]]:
    pending = [
        dict(item)
        for item in queue_items
        if str(item.get("status") or "").casefold() in {"queued", "sending"}
    ]
    pending.sort(
        key=lambda item: (
            0 if str(item.get("status") or "").casefold() == "sending" else 1,
            int(item.get("scheduled_at") or 0),
            int(item.get("id") or 0),
        )
    )

    now = time.time()
    available_at = now + max(0.0, global_wait_seconds)
    result: dict[str, dict[str, Any]] = {}
    for item in pending:
        phone = str(item.get("phone") or "")
        status = str(item.get("status") or "").casefold()
        if not phone:
            continue
        if status == "sending":
            item["estimated_at"] = int(now)
            result[phone] = item
            continue
        estimated_at = max(float(item.get("scheduled_at") or 0), available_at)
        item["estimated_at"] = int(estimated_at)
        result[phone] = item
        if worker_enabled:
            available_at = estimated_at + max(1.0, global_gap_seconds)
    return result


def queue_countdown(item: dict[str, Any] | None, worker_enabled: bool) -> tuple[str, str]:
    if not item:
        return "READY", GREEN
    status = str(item.get("status") or "").casefold()
    if status == "sending":
        return "SENDING", CYAN
    if status != "queued":
        return status.upper() or "-", DIM
    if not worker_enabled:
        return "PAUSED", YELLOW

    remaining = int(item.get("estimated_at") or item.get("scheduled_at") or 0) - int(time.time())
    if remaining <= 0:
        return "DUE", CYAN
    minutes, seconds = divmod(remaining, 60)
    if minutes >= 100:
        return f"WAIT {minutes}m", YELLOW
    return f"WAIT {minutes:02d}:{seconds:02d}", YELLOW


def number_rows(
    messages: list[dict[str, Any]],
    pending: dict[str, dict[str, Any]],
    worker_enabled: bool,
) -> list[dict[str, Any]]:
    contacts = {str(row["phone"]): row for row in list_contacts(limit=500)}
    permitted = allowed_recipients()
    activity = recent_activity_by_phone(messages)
    maximum = int(os.getenv("WA_MAX_REPLIES_PER_CONTACT_PER_DAY", "6") or 6)

    phones = sorted(set(contacts) | permitted, key=lambda value: (contacts.get(value, {}).get("display_name", ""), value))
    rows: list[dict[str, Any]] = []
    for index, phone in enumerate(phones, start=1):
        contact = contacts.get(phone)
        count = replies_today(phone, day_key())
        if contact and contact.get("opted_out_at") is not None and not int(contact.get("opted_in") or 0):
            status = "OPT-OUT"
            status_color = RED
        elif maximum >= 0 and count >= maximum:
            status = "LIMIT"
            status_color = YELLOW
        elif contact and int(contact.get("opted_in") or 0):
            status = "READY"
            status_color = GREEN
        elif phone in permitted:
            status = "ALLOWLIST"
            status_color = CYAN
        else:
            status = "DISABLED"
            status_color = RED

        next_text, next_color = queue_countdown(pending.get(phone), worker_enabled)
        display_name = str((contact or {}).get("display_name") or f"contact{index}").strip()
        rows.append(
            {
                "name": display_name,
                "phone": phone,
                "status": status,
                "status_color": status_color,
                "usage": f"{count}/{maximum if maximum >= 0 else '∞'}",
                "next": next_text,
                "next_color": next_color,
                "last": human_time(activity.get(phone)),
            }
        )
    return rows


def combined_activity(messages: list[dict[str, Any]], queue_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for item in messages:
        direction = "IN" if item.get("direction") == "incoming" else "OUT"
        phone = str(item.get("phone") or "")
        status = str(item.get("status") or "-").upper()
        events.append(
            {
                "timestamp": int(item.get("updated_at") or item.get("created_at") or 0),
                "text": f"{direction} ..{phone[-4:]} {status} {item.get('body') or ''}".strip(),
            }
        )
    for item in queue_items:
        phone = str(item.get("phone") or "")
        status = str(item.get("status") or "-").upper()
        events.append(
            {
                "timestamp": int(item.get("updated_at") or item.get("created_at") or 0),
                "text": f"QUEUE ..{phone[-4:]} {status} {item.get('body') or ''}".strip(),
            }
        )
    return sorted(events, key=lambda item: int(item["timestamp"]), reverse=True)


def render() -> None:
    clear_screen()
    terminal_width = max(100, min(shutil.get_terminal_size((132, 34)).columns, 160))
    messages = list_messages(limit=70)
    queue_items = list_queue(limit=500)
    message_stats = status_summary()
    queue_stats = queue_summary()
    service, health = server_status()
    worker = health.get("queue_worker", {}) if health else {}
    worker_enabled = bool(worker.get("enabled", False))
    global_gap = float(worker.get("global_gap_seconds", os.getenv("WA_QUEUE_GLOBAL_GAP_SECONDS", "15")) or 15)
    global_wait = float(worker.get("global_wait_seconds", 0) or 0)
    pending = estimated_pending_by_phone(
        queue_items,
        worker_enabled=worker_enabled,
        global_gap_seconds=global_gap,
        global_wait_seconds=global_wait,
    )
    rows = number_rows(messages, pending, worker_enabled)

    service_color = GREEN if service == "RUNNING" else RED
    total_messages = sum(message_stats.values())
    failed = message_stats.get("failed", 0) + queue_stats.get("failed", 0)
    waiting = queue_stats.get("queued", 0)
    sending = queue_stats.get("sending", 0)
    sent = queue_stats.get("sent", 0)

    print(color("WA CONTACT & MESSAGE MONITOR", CYAN))
    print(color("Manual opt-in contacts • one pending message per contact • no bulk/broadcast command", DIM))
    print("=" * terminal_width)
    print(
        f" Service: {color(service, service_color):<22}"
        f" Mode: {color(mode().upper(), CYAN):<18}"
        f" Contacts: {len(rows):<5} Messages: {total_messages:<6} Failed: {failed}"
    )
    print(
        f" Queue: {color(str(waiting), YELLOW)} waiting | {color(str(sending), CYAN)} sending | "
        f"{color(str(sent), GREEN)} sent | Worker: {color('ON' if worker_enabled else 'PAUSED', GREEN if worker_enabled else YELLOW)}"
    )
    if health:
        cooldown = health.get("cooldown_seconds", {})
        gap = global_gap
        print(
            f" Auto-reply delay: {cooldown.get('minimum', '-')}–{cooldown.get('maximum', '-')} sec"
            f"   Queue global gap: {gap} sec"
            f"   Daily/contact: {os.getenv('WA_MAX_REPLIES_PER_CONTACT_PER_DAY', '6')}"
        )
    print("-" * terminal_width)

    left_width = min(78, max(68, terminal_width // 2 + 6))
    right_width = terminal_width - left_width - 3
    print(f"{'CONTACTS / NEXT DELIVERY':^{left_width}} | {'LIVE MESSAGE & QUEUE ACTIVITY':^{right_width}}")
    print(
        f"{'Contact':<15} {'Phone':<16} {'State':<10} {'Today':<7} {'Next':<12} {'Last':<8}"
        f" | {'Time':<9} {'Event':<{max(10, right_width-10)}}"
    )
    print(f"{'-' * left_width}-+-{'-' * right_width}")

    events = combined_activity(messages, queue_items)
    activity_lines: list[str] = []
    for item in events[:28]:
        event = clip(item["text"], max(8, right_width - 10))
        activity_lines.append(f"{human_time(int(item['timestamp'])):<9} {event}")

    line_count = max(14, min(28, max(len(rows), len(activity_lines), 14)))
    for index in range(line_count):
        if index < len(rows):
            row = rows[index]
            state_cell = color(f"{row['status']:<10}", row["status_color"])
            next_cell = color(f"{row['next']:<12}", row["next_color"])
            left = (
                f"{clip(row['name'], 15):<15} "
                f"{clip(row['phone'], 16):<16} "
                f"{state_cell} "
                f"{row['usage']:<7} "
                f"{next_cell} "
                f"{row['last']:<8}"
            )
        else:
            left = " " * left_width
        right = activity_lines[index] if index < len(activity_lines) else ""
        print(f"{left} | {right}")

    print("-" * terminal_width)
    print(" [A] Add contact  [E] Edit name  [M] Queue message  [C] Cancel waiting  [O] Opt-out  [R] Refresh  [Q] Quit")
    print(color("Target contact is entered in the Contact field. Queue accepts one message per opted-in contact.", DIM))
    if mode() == "meta" and not worker_enabled:
        print(color("META queue delivery is paused. Set WA_QUEUE_REAL_SEND_ENABLED=true only after official setup is valid.", YELLOW))


def resolve_contact(value: str) -> dict[str, Any] | None:
    raw = value.strip()
    if not raw:
        return None

    contacts = list_contacts(limit=500)
    try:
        phone = normalize_phone(raw)
    except ValueError:
        phone = ""
    if phone:
        direct = get_contact(phone)
        if direct:
            return direct

    matches = [
        contact
        for contact in contacts
        if str(contact.get("display_name") or "").strip().casefold() == raw.casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def prompt_add() -> None:
    clear_screen()
    print("ADD / OPT-IN CONTACT")
    print("Only add contacts that have given permission. International number example: 60123456789")
    display_name = input("Contact name: ").strip()
    raw = input("Phone number: ").strip()
    try:
        phone = normalize_phone(raw)
    except ValueError as exc:
        input(f"Error: {exc}. Press Enter...")
        return
    source = input("Consent source [cmd-manual]: ").strip() or "cmd-manual"
    note = input("Consent note: ").strip()
    set_opt_in(phone, source=source, note=note, display_name=display_name)
    input(f"Contact {display_name or phone} ({phone}) is READY. Press Enter...")


def prompt_edit_name() -> None:
    clear_screen()
    print("EDIT CONTACT NAME")
    raw = input("Existing contact name or phone: ").strip()
    contact = resolve_contact(raw)
    if not contact:
        input("Contact not found or name is not unique. Press Enter...")
        return
    new_name = input("New contact name: ").strip()
    if not new_name:
        input("Name cannot be empty. Press Enter...")
        return
    update_display_name(str(contact["phone"]), new_name)
    input(f"Contact name updated to {new_name}. Press Enter...")


def prompt_queue_message() -> None:
    clear_screen()
    print("QUEUE ONE MESSAGE")
    print("The target must be an opted-in contact. No bulk queue is available.")
    raw = input("Contact name or phone: ").strip()
    contact = resolve_contact(raw)
    if not contact:
        input("Contact not found. Add it first with [A]. Press Enter...")
        return
    if int(contact.get("opted_in") or 0) != 1:
        input("Contact is not opted in. Press Enter...")
        return

    message = input("Message: ").strip()
    if not message:
        input("Message cannot be empty. Press Enter...")
        return

    minimum = max(1, int(os.getenv("WA_QUEUE_MIN_DELAY_SECONDS", "15") or 15))
    default_delay = max(minimum, int(os.getenv("WA_QUEUE_DEFAULT_DELAY_SECONDS", "30") or 30))
    raw_delay = input(f"Wait before delivery in seconds [{default_delay}, minimum {minimum}]: ").strip()
    try:
        delay = int(raw_delay) if raw_delay else default_delay
    except ValueError:
        input("Delay must be an integer. Press Enter...")
        return
    delay = max(minimum, delay)

    try:
        item_id = enqueue_message(str(contact["phone"]), message, delay)
    except ValueError as exc:
        input(f"Cannot queue: {exc}. Press Enter...")
        return

    input(
        f"Queue #{item_id} for {contact.get('display_name') or contact['phone']} "
        f"will be due in {delay} seconds. Press Enter..."
    )


def prompt_cancel() -> None:
    clear_screen()
    print("CANCEL WAITING MESSAGE")
    raw = input("Contact name or phone: ").strip()
    contact = resolve_contact(raw)
    if not contact:
        input("Contact not found. Press Enter...")
        return
    total = cancel_pending(str(contact["phone"]))
    input(f"Cancelled {total} waiting message(s). Press Enter...")


def prompt_opt_out() -> None:
    clear_screen()
    print("OPT-OUT CONTACT")
    raw = input("Contact name or phone: ").strip()
    contact = resolve_contact(raw)
    if contact:
        phone = str(contact["phone"])
    else:
        try:
            phone = normalize_phone(raw)
        except ValueError as exc:
            input(f"Error: {exc}. Press Enter...")
            return
    cancel_pending(phone)
    set_opt_out(phone)
    input(f"Contact {phone} is OPT-OUT and waiting messages were cancelled. Press Enter...")


def read_key_windows(timeout: float) -> str | None:
    import msvcrt

    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if msvcrt.kbhit():
            key = msvcrt.getwch()
            return key.casefold()
        time.sleep(0.05)
    return None


def main() -> int:
    enable_terminal()
    init_database()
    init_contact_store()
    init_queue_store()
    refresh = max(0.5, float(os.getenv("WA_MONITOR_REFRESH_SECONDS", "1") or 1))

    if os.name != "nt":
        print("Interactive key controls are optimized for Windows CMD.")
        print("Use: python wa_monitor.py --once for a single snapshot.")

    if "--once" in sys.argv:
        render()
        return 0

    try:
        while True:
            render()
            if os.name == "nt":
                key = read_key_windows(refresh)
            else:
                time.sleep(refresh)
                key = None

            if key == "q":
                break
            if key == "a":
                prompt_add()
            elif key == "e":
                prompt_edit_name()
            elif key == "m":
                prompt_queue_message()
            elif key == "c":
                prompt_cancel()
            elif key == "o":
                prompt_opt_out()
            elif key == "r":
                continue
    except KeyboardInterrupt:
        pass
    finally:
        print(RESET, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
