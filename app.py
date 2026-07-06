from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from contact_store import increment_reply_counter, init_contact_store, replies_today
from cooldown import ReplyCooldown
from queue_store import init_queue_store, list_queue, queue_summary
from queue_worker import OutboundQueueWorker
from status_parser import extract_delivery_statuses
from storage import (
    database_health,
    init_database,
    list_messages,
    message_exists,
    save_message,
    status_summary,
)
from wa_client import (
    allowed_recipients,
    mode as runtime_mode,
    normalize_phone,
    required_env,
    send_allowed_reply,
)

load_dotenv(Path(__file__).resolve().with_name(".env"))

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("wa-system")


def env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number") from exc


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


def current_day_key() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


cooldown = ReplyCooldown(
    minimum_seconds=env_float("WA_COOLDOWN_MIN_SECONDS", 16.0),
    maximum_seconds=env_float("WA_COOLDOWN_MAX_SECONDS", 20.0),
)
queue_worker = OutboundQueueWorker()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    init_contact_store()
    init_queue_store()
    await queue_worker.start()
    try:
        yield
    finally:
        await queue_worker.shutdown()
        await cooldown.shutdown()


app = FastAPI(
    title="WA Opt-in Message Monitor",
    version="2.1.0",
    lifespan=lifespan,
)


def is_valid_signature(raw_body: bytes, signature_header: str | None) -> bool:
    app_secret = os.getenv("WA_APP_SECRET", "").strip()
    if not app_secret:
        if runtime_mode() == "offline":
            logger.debug("Webhook signature validation skipped in OFFLINE mode")
            return True
        logger.error("WA_APP_SECRET is required for webhook validation in META mode")
        return False
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    supplied = signature_header.removeprefix("sha256=")
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(supplied, expected)


def parse_timestamp(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def extract_incoming_texts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for entry in _as_list(payload.get("entry")):
        if not isinstance(entry, dict):
            continue
        for change in _as_list(entry.get("changes")):
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            for message in _as_list(value.get("messages")):
                if not isinstance(message, dict) or message.get("type") != "text":
                    continue

                message_id = message.get("id")
                sender = message.get("from")
                text = message.get("text")
                body = text.get("body") if isinstance(text, dict) else None
                if not message_id or not sender or not body:
                    continue

                try:
                    normalized_sender = normalize_phone(str(sender))
                except ValueError:
                    logger.warning("Ignoring incoming message with an invalid sender number")
                    continue

                result.append(
                    {
                        "message_id": str(message_id),
                        "sender": normalized_sender,
                        "body": str(body).strip(),
                        "timestamp": parse_timestamp(message.get("timestamp")),
                        "raw": message,
                    }
                )
    return result


def _response_data() -> dict[str, Any]:
    configured = os.getenv("WA_RESPONSE_DATA_PATH", "response_data.json").strip()
    path = Path(configured)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def reply_text(incoming_text: str) -> str:
    normalized = incoming_text.casefold()

    rules_raw = os.getenv("WA_AUTO_REPLY_RULES", "").strip()
    if rules_raw:
        try:
            rules = json.loads(rules_raw)
        except json.JSONDecodeError:
            logger.exception("WA_AUTO_REPLY_RULES is invalid JSON")
        else:
            if isinstance(rules, dict):
                for keyword, response in rules.items():
                    if str(keyword).casefold() in normalized and str(response).strip():
                        return str(response).strip()

    response_data = _response_data()
    response_rules = response_data.get("rules", [])
    for rule in response_rules if isinstance(response_rules, list) else []:
        if not isinstance(rule, dict):
            continue
        keywords = rule.get("keywords", [])
        response = str(rule.get("response") or "").strip()
        if response and isinstance(keywords, list) and any(
            str(keyword).casefold() in normalized for keyword in keywords
        ):
            return response

    configured_default = os.getenv("WA_AUTO_REPLY_TEXT", "").strip()
    if configured_default:
        return configured_default
    return str(
        response_data.get("default")
        or "Balasan otomatis: Terima kasih, pesan Anda sudah diterima."
    ).strip()


async def send_and_record(recipient: str, message: str) -> None:
    try:
        result = await send_allowed_reply(recipient, message)
    except (httpx.HTTPError, RuntimeError, ValueError, PermissionError) as exc:
        logger.exception(
            "Automatic reply failed for recipient ending %s: %s",
            recipient[-4:],
            exc,
        )
        return

    outgoing_status = "simulated" if result.get("mode") == "offline" else "accepted"
    recorded = False
    for item in result.get("messages", []) or []:
        if not isinstance(item, dict):
            continue
        message_id = item.get("id")
        if not message_id:
            continue
        save_message(
            message_id=str(message_id),
            direction="outgoing",
            phone=recipient,
            body=message,
            status=outgoing_status,
            raw=result,
        )
        recorded = True

    if recorded:
        increment_reply_counter(recipient, current_day_key())


def require_admin(value: str | None) -> None:
    expected = os.getenv("WA_ADMIN_API_KEY", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="WA_ADMIN_API_KEY is not configured")
    if not value or not hmac.compare_digest(value, expected):
        raise HTTPException(status_code=401, detail="Invalid admin API key")


@app.get("/health")
async def health() -> dict[str, Any]:
    database = database_health()
    return {
        "status": "ok" if database.get("ok") else "degraded",
        "mode": runtime_mode(),
        "database": database,
        "cooldown_seconds": {
            "minimum": cooldown.minimum_seconds,
            "maximum": cooldown.maximum_seconds,
        },
        "allowed_recipient_count": len(allowed_recipients()),
        "message_summary": status_summary(),
        "queue_summary": queue_summary(),
        "queue_worker": queue_worker.state(),
    }


@app.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> str:
    expected = os.getenv("WA_VERIFY_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="WA_VERIFY_TOKEN is not configured")
    if mode == "subscribe" and token and hmac.compare_digest(token, expected):
        return challenge or ""
    raise HTTPException(status_code=403, detail="Webhook verification failed")


@app.post("/webhook")
async def webhook(request: Request) -> dict[str, int | str]:
    raw_body = await request.body()
    if not is_valid_signature(raw_body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook payload must be a JSON object")

    incoming_count = 0
    scheduled_count = 0
    status_count = 0
    max_replies_per_day = env_int("WA_MAX_REPLIES_PER_CONTACT_PER_DAY", 6)

    for status in extract_delivery_statuses(payload):
        save_message(
            message_id=status["message_id"],
            direction="outgoing",
            phone=status["recipient_id"],
            body="",
            status=status["status"],
            event_timestamp=status["timestamp"],
            error=status["error"],
            raw=status["raw"],
        )
        status_count += 1

    permitted = allowed_recipients()
    for incoming in extract_incoming_texts(payload):
        incoming_count += 1
        if message_exists(incoming["message_id"]):
            logger.info("Duplicate webhook ignored: %s", incoming["message_id"])
            continue

        save_message(
            message_id=incoming["message_id"],
            direction="incoming",
            phone=incoming["sender"],
            body=incoming["body"],
            status="received",
            event_timestamp=incoming["timestamp"],
            raw=incoming["raw"],
        )

        if incoming["sender"] not in permitted:
            logger.info("Incoming number is not opted in or allowlisted")
            continue

        response = reply_text(incoming["body"])
        if not response:
            continue

        if (
            max_replies_per_day >= 0
            and replies_today(incoming["sender"], current_day_key()) >= max_replies_per_day
        ):
            logger.info(
                "Daily automatic reply cap reached for recipient ending %s",
                incoming["sender"][-4:],
            )
            continue

        cooldown.schedule(incoming["sender"], response, send_and_record)
        scheduled_count += 1

    return {
        "status": "accepted",
        "incoming_messages": incoming_count,
        "scheduled_replies": scheduled_count,
        "delivery_updates": status_count,
    }


@app.get("/messages")
async def messages(
    limit: int = Query(default=100, ge=1, le=500),
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
) -> dict[str, Any]:
    require_admin(x_admin_key)
    return {
        "items": list_messages(limit),
        "summary": status_summary(),
        "note": "Delivery status is available; arbitrary user online/active presence is not.",
    }


@app.get("/queue")
async def queue_items(
    limit: int = Query(default=100, ge=1, le=500),
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
) -> dict[str, Any]:
    require_admin(x_admin_key)
    return {
        "items": list_queue(limit),
        "summary": queue_summary(),
        "worker": queue_worker.state(),
    }
