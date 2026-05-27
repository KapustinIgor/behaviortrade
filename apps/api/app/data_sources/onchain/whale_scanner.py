from __future__ import annotations

"""Whale transaction scanner using blockchain.info unconfirmed-transactions feed."""

import logging
import time

import httpx

from app.core.redis_client import get_json, set_json

logger = logging.getLogger(__name__)

_BASE = "https://blockchain.info"
_CACHE_KEY = "whale_txs_live"
_TTL = 300  # 5 minutes


async def fetch_whale_transactions(min_btc: float = 10.0) -> list[dict]:
    """Fetch recent large unconfirmed BTC transactions from blockchain.info.

    Returns up to 20 transactions where total output >= *min_btc* BTC, each as::

        {"hash": str, "btc": float, "direction": "unknown", "ts": int}

    Results are cached in Redis under ``whale_txs_live`` with a 5-minute TTL.
    Falls back to cached data on error.
    """
    # Try cache first
    cached = await get_json(_CACHE_KEY)
    if cached and isinstance(cached, list):
        return cached

    result: list[dict] = []
    try:
        async with httpx.AsyncClient(base_url=_BASE, timeout=20.0) as client:
            r = await client.get(
                "/unconfirmed-transactions",
                params={"format": "json", "limit": 100},
            )
            if not r.is_success:
                logger.warning("blockchain.info unconfirmed-transactions returned %d", r.status_code)
                return []

            txs = r.json().get("txs", [])

        now = int(time.time())
        for tx in txs:
            outputs = tx.get("out", [])
            total_sat = sum(o.get("value", 0) for o in outputs)
            total_btc = total_sat / 1e8
            if total_btc < min_btc:
                continue
            ts = tx.get("time", now)
            result.append({
                "hash": tx.get("hash", ""),
                "btc": round(total_btc, 4),
                "direction": "unknown",
                "ts": ts,
            })

        result.sort(key=lambda x: x["btc"], reverse=True)
        result = result[:20]

        if result:
            try:
                await set_json(_CACHE_KEY, result, ttl=_TTL)
            except Exception as exc:
                logger.warning("Failed to cache whale_txs_live: %s", exc)

    except Exception as exc:
        logger.warning("Whale scanner fetch error: %s", exc)

    return result
