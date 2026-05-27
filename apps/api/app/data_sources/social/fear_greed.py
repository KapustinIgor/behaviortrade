from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

_URL = "https://api.alternative.me/fng/"


async def get_fear_greed(limit: int = 30) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(_URL, params={"limit": limit, "format": "json"})
            r.raise_for_status()
            payload = r.json()
        except httpx.HTTPError as e:
            logger.warning("Fear & Greed fetch error: %s", e)
            return {"value": 50, "value_classification": "Neutral", "last_30_days": []}

    data = payload.get("data", [])
    if not data:
        return {"value": 50, "value_classification": "Neutral", "last_30_days": []}

    latest = data[0]
    history = [
        {
            "value": int(d["value"]),
            "classification": d["value_classification"],
            "timestamp": datetime.fromtimestamp(int(d["timestamp"]), tz=timezone.utc).isoformat(),
        }
        for d in data
    ]

    return {
        "value": int(latest["value"]),
        "value_classification": latest["value_classification"],
        "timestamp": datetime.fromtimestamp(int(latest["timestamp"]), tz=timezone.utc).isoformat(),
        "last_30_days": history,
    }
