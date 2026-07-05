from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def response_path() -> Path:
    configured = os.getenv("WA_RESPONSE_DATA_PATH", "").strip()
    return Path(configured) if configured else Path(__file__).with_name("response_data.json")


def load_responses() -> dict[str, Any]:
    with response_path().open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise RuntimeError("Response data must be a JSON object")
    return data


def select_response(message: str) -> tuple[str, str]:
    data = load_responses()
    normalized = message.casefold()
    rules = data.get("rules", [])

    if isinstance(rules, list):
        for index, rule in enumerate(rules):
            if not isinstance(rule, dict):
                continue
            keywords = rule.get("keywords", [])
            response = str(rule.get("response", "")).strip()
            if response and isinstance(keywords, list):
                if any(str(keyword).casefold() in normalized for keyword in keywords):
                    return f"rule:{index}", response

    return "default", str(data.get("default", "")).strip()


def list_response_rules() -> list[dict[str, Any]]:
    data = load_responses()
    rules = data.get("rules", [])
    return rules if isinstance(rules, list) else []
