from __future__ import annotations

import argparse
import asyncio
import os
import py_compile
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"


class Reporter:
    def __init__(self) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = LOG_DIR / f"system_check_{stamp}.log"
        self._file = self.path.open("w", encoding="utf-8")

    def write(self, text: str = "") -> None:
        print(text)
        self._file.write(text + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def check_files() -> None:
    required = [
        "app.py",
        "wa_client.py",
        "wa_monitor.py",
        "contact_store.py",
        "queue_store.py",
        "queue_worker.py",
        "storage.py",
        "requirements.txt",
        "setup_windows.bat",
        "run_server.bat",
        "run_monitor.bat",
        "run_wa_bot.bat",
    ]
    missing = [name for name in required if not (ROOT / name).is_file()]
    require(not missing, f"Missing required files: {', '.join(missing)}")


def check_python() -> None:
    require(sys.version_info >= (3, 11), "Python 3.11 or newer is required")


def check_compile() -> None:
    files = sorted(ROOT.glob("*.py"))
    require(bool(files), "No Python files found")
    for path in files:
        py_compile.compile(str(path), doraise=True)


def check_batch_files() -> None:
    run_bot = (ROOT / "run_wa_bot.bat").read_text(encoding="utf-8").casefold()
    run_server = (ROOT / "run_server.bat").read_text(encoding="utf-8").casefold()
    require("setup_windows.bat" in run_bot, "run_wa_bot.bat does not call setup")
    require("run_monitor.bat" in run_bot, "run_wa_bot.bat does not start the monitor")
    require("uvicorn" in run_server and "app:app" in run_server, "run_server.bat is invalid")


async def offline_integration() -> None:
    managed = {
        "WA_DB_PATH": None,
        "WA_MODE": "offline",
        "WA_ALLOWED_RECIPIENTS": "",
        "WA_QUEUE_PROCESS_ENABLED": "true",
        "WA_QUEUE_POLL_SECONDS": "0.25",
        "WA_QUEUE_GLOBAL_GAP_SECONDS": "1",
        "WA_MAX_REPLIES_PER_CONTACT_PER_DAY": "6",
        "WA_COOLDOWN_MIN_SECONDS": "0",
        "WA_COOLDOWN_MAX_SECONDS": "0",
    }
    original = {name: os.environ.get(name) for name in managed}

    with tempfile.TemporaryDirectory(prefix="wa-system-check-") as temporary:
        managed["WA_DB_PATH"] = str(Path(temporary) / "system-check.db")
        for name, value in managed.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

        try:
            from app import app, health
            from contact_store import set_opt_in
            from queue_store import enqueue_message, list_queue
            from storage import list_messages

            async with app.router.lifespan_context(app):
                phone = "60100000001"
                set_opt_in(
                    phone,
                    source="system-check",
                    note="Temporary offline integration contact",
                    display_name="System Check",
                )
                enqueue_message(phone, "offline integration check", 1)

                deadline = time.monotonic() + 8
                latest = None
                while time.monotonic() < deadline:
                    rows = list_queue(limit=10)
                    latest = rows[0] if rows else None
                    if latest and latest["status"] in {"sent", "failed", "blocked"}:
                        break
                    await asyncio.sleep(0.25)

                require(latest is not None, "Queue item was not created")
                require(latest["status"] == "sent", f"Queue ended with status {latest['status']}")

                messages = list_messages(limit=20)
                outgoing = [item for item in messages if item["direction"] == "outgoing"]
                require(bool(outgoing), "No outgoing offline log was recorded")
                require(outgoing[0]["phone"] == phone, "Outgoing log has the wrong phone")

                result = await health()
                require(result["status"] == "ok", f"Health status is {result['status']}")
                require(result["database"]["ok"] is True, "SQLite quick_check failed")
                require(result["queue_worker"]["enabled"] is True, "Queue worker is disabled")
        finally:
            for name, value in original.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value


def run_pytest(reporter: Reporter) -> None:
    process = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if process.stdout.strip():
        reporter.write(process.stdout.rstrip())
    if process.stderr.strip():
        reporter.write(process.stderr.rstrip())
    require(process.returncode == 0, f"pytest returned exit code {process.returncode}")


def run_step(reporter: Reporter, name: str, callback: Callable[[], None]) -> None:
    started = time.monotonic()
    reporter.write(f"[RUN ] {name}")
    callback()
    reporter.write(f"[PASS] {name} ({time.monotonic() - started:.2f}s)")


def main() -> int:
    parser = argparse.ArgumentParser(description="WA system local validation")
    parser.add_argument("--quick", action="store_true", help="Skip the pytest suite")
    args = parser.parse_args()

    reporter = Reporter()
    reporter.write("WA BOT SYSTEM CHECK")
    reporter.write(f"Python: {sys.version.split()[0]}")
    reporter.write(f"Root: {ROOT}")
    reporter.write("Mode: OFFLINE TEST ONLY")
    reporter.write("")

    try:
        run_step(reporter, "Python version", check_python)
        run_step(reporter, "Required project files", check_files)
        run_step(reporter, "Windows CMD scripts", check_batch_files)
        run_step(reporter, "Python compilation", check_compile)
        run_step(reporter, "Offline service and queue integration", lambda: asyncio.run(offline_integration()))
        if not args.quick:
            run_step(reporter, "Pytest suite", lambda: run_pytest(reporter))
    except Exception as exc:
        reporter.write("")
        reporter.write(f"[FAIL] {type(exc).__name__}: {exc}")
        reporter.write(f"Log: {reporter.path}")
        reporter.close()
        return 1

    reporter.write("")
    reporter.write("[PASS] All checks completed successfully")
    reporter.write(f"Log: {reporter.path}")
    reporter.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
