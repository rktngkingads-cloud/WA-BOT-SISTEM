from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone

import httpx

from contact_store import increment_reply_counter, is_opted_in, replies_today
from queue_store import claim_due_message, init_queue_store, mark_queue_item, requeue_sending_items
from storage import save_message
from wa_client import mode, send_allowed_reply

logger = logging.getLogger("wa-system.queue")


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number") from exc


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


def current_day_key() -> str:
    return datetime.now(timezone.utc).date().isoformat()


class OutboundQueueWorker:
    """Processes one manually queued, opted-in contact at a time.

    OFFLINE mode simulates sends. Real Meta queue sending remains disabled unless
    WA_QUEUE_REAL_SEND_ENABLED=true is explicitly configured.
    """

    def __init__(self) -> None:
        self.poll_seconds = max(0.25, _env_float("WA_QUEUE_POLL_SECONDS", 0.5))
        self.global_gap_seconds = max(1.0, _env_float("WA_QUEUE_GLOBAL_GAP_SECONDS", 15.0))
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._last_send_at = 0.0

    @property
    def enabled(self) -> bool:
        if not _env_bool("WA_QUEUE_PROCESS_ENABLED", True):
            return False
        if mode() == "offline":
            return True
        return _env_bool("WA_QUEUE_REAL_SEND_ENABLED", False)

    def state(self) -> dict[str, object]:
        global_wait = max(0.0, self.global_gap_seconds - (time.monotonic() - self._last_send_at))
        return {
            "enabled": self.enabled,
            "mode": mode(),
            "poll_seconds": self.poll_seconds,
            "global_gap_seconds": self.global_gap_seconds,
            "global_wait_seconds": round(global_wait, 1),
            "real_send_enabled": _env_bool("WA_QUEUE_REAL_SEND_ENABLED", False),
        }

    async def start(self) -> None:
        init_queue_store()
        recovered = requeue_sending_items()
        if recovered:
            logger.warning("Recovered %s queue item(s) after restart", recovered)
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="wa-outbound-queue")

    async def shutdown(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            if not self.enabled:
                await asyncio.sleep(self.poll_seconds)
                continue

            remaining_gap = self.global_gap_seconds - (time.monotonic() - self._last_send_at)
            if remaining_gap > 0:
                await asyncio.sleep(min(remaining_gap, self.poll_seconds))
                continue

            item = claim_due_message()
            if item is None:
                await asyncio.sleep(self.poll_seconds)
                continue

            await self._process(item)

    async def _process(self, item: dict[str, object]) -> None:
        item_id = int(item["id"])
        phone = str(item["phone"])
        body = str(item["body"])

        # Queue messages require an explicit database opt-in; an env allowlist alone
        # is not enough for manually scheduled outbound delivery.
        if not is_opted_in(phone):
            mark_queue_item(item_id, "blocked", error="Contact is not opted in")
            logger.warning("Blocked queued message for non-opted-in contact ending %s", phone[-4:])
            return

        maximum = _env_int("WA_MAX_REPLIES_PER_CONTACT_PER_DAY", 6)
        if maximum >= 0 and replies_today(phone, current_day_key()) >= maximum:
            mark_queue_item(item_id, "blocked", error="Daily per-contact limit reached")
            logger.info("Daily queue limit reached for contact ending %s", phone[-4:])
            return

        try:
            result = await send_allowed_reply(phone, body)
        except (httpx.HTTPError, RuntimeError, ValueError, PermissionError) as exc:
            mark_queue_item(item_id, "failed", error=str(exc))
            logger.exception("Queued send failed for contact ending %s", phone[-4:])
            return

        messages = result.get("messages", []) if isinstance(result, dict) else []
        message_id = ""
        if messages and isinstance(messages[0], dict):
            message_id = str(messages[0].get("id") or "")

        if not message_id:
            mark_queue_item(item_id, "failed", error="Provider returned no message id")
            return

        save_message(
            message_id=message_id,
            direction="outgoing",
            phone=phone,
            body=body,
            status="accepted",
            raw=result,
        )
        increment_reply_counter(phone, current_day_key())
        mark_queue_item(item_id, "sent", message_id=message_id)
        self._last_send_at = time.monotonic()
        logger.info("Queued message sent for contact ending %s", phone[-4:])
