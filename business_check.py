from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx

from wa_client import required_env


async def fetch_configured_resource() -> dict[str, Any]:
    graph_version = required_env("WA_GRAPH_API_VERSION")
    phone_number_id = required_env("WA_PHONE_NUMBER_ID")
    access_token = required_env("WA_ACCESS_TOKEN")
    fields = os.getenv(
        "WA_ACCOUNT_STATUS_FIELDS",
        "id,display_phone_number,verified_name,quality_rating",
    ).strip()

    url = f"https://graph.facebook.com/{graph_version}/{phone_number_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"fields": fields}

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

    return {
        "api_reachable": True,
        "phone_number_id": phone_number_id,
        "metadata": data,
    }


async def safe_resource_check() -> dict[str, Any]:
    required = ("WA_GRAPH_API_VERSION", "WA_PHONE_NUMBER_ID", "WA_ACCESS_TOKEN")
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if missing:
        return {
            "configured": False,
            "api_reachable": False,
            "missing_environment": missing,
        }

    try:
        result = await fetch_configured_resource()
    except httpx.HTTPStatusError as exc:
        return {
            "configured": True,
            "api_reachable": False,
            "http_status": exc.response.status_code,
            "error": exc.response.text[:1000],
        }
    except (httpx.HTTPError, RuntimeError) as exc:
        return {
            "configured": True,
            "api_reachable": False,
            "error": str(exc),
        }

    return {"configured": True, **result}


def main() -> int:
    result = asyncio.run(safe_resource_check())
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("api_reachable") else 1


if __name__ == "__main__":
    raise SystemExit(main())
