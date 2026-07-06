from __future__ import annotations

import logging
import os
import sqlite3
import uuid
from typing import Any

import httpx

logger = logging.getLogger("wa-system.client")


def normalize_phone(value: str) -> str:
    """Return an international phone number containing digits only."""
    normalized = "".join(character for character in str(value) if character.isdigit())
    if not normalized:
        raise ValueError("Phone number is empty or invalid")
    if normalized.startswith("00"):
        normalized = normalized[2:]
    return normalized


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def mode() -> str:
    selected = os.getenv("WA_MODE", "offline").strip().casefold() or "offline"
    if selected not in {"offline", "meta"}:
        raise RuntimeError("WA_MODE must be 'offline' or 'meta'")
    return selected


def _environment_recipients() -> set[str]:
    raw = os.getenv("WA_ALLOWED_RECIPIENTS", "")
    recipients: set[str] = set()
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            recipients.add(normalize_phone(item))
        except ValueError:
            logger.warning("Ignoring invalid number in WA_ALLOWED_RECIPIENTS")
    return recipients


def allowed_recipients() -> set[str]:
    """Combine the bootstrap allowlist with database opt-ins.

    A recorded opt-out overrides the environment allowlist.
    """
    recipients = _environment_recipients()

    try:
        from contact_store import init_contact_store, list_contacts

        init_contact_store()
        for contact in list_contacts(limit=500):
            phone = normalize_phone(str(contact["phone"]))
            if int(contact.get("opted_in") or 0) == 1:
                recipients.add(phone)
            elif contact.get("opted_out_at") is not None:
                recipients.discard(phone)
    except (ImportError, KeyError, sqlite3.Error, ValueError):
        logger.exception("Unable to load database contact permissions")

    return recipients


async def send_allowed_reply(recipient: str, message: str) -> dict[str, Any]:
    recipient = normalize_phone(recipient)
    if recipient not in allowed_recipients():
        raise PermissionError("Recipient is not opted in or allowlisted")

    text = str(message).strip()
    if not text:
        raise ValueError("Reply message is empty")

    if mode() == "offline":
        message_id = f"offline.{uuid.uuid4().hex}"
        logger.info("OFFLINE reply simulated for recipient ending %s", recipient[-4:])
        return {
            "messaging_product": "whatsapp",
            "mode": "offline",
            "contacts": [{"input": recipient, "wa_id": recipient}],
            "messages": [{"id": message_id}],
        }

    version = required_env("WA_GRAPH_API_VERSION")
    phone_number_id = required_env("WA_PHONE_NUMBER_ID")
    access_token = required_env("WA_ACCESS_TOKEN")
    endpoint = f"https://graph.facebook.com/{version}/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()

    if not isinstance(result, dict):
        raise RuntimeError("Unexpected WhatsApp API response")
    return result
