from __future__ import annotations

"""CoinGecko exchange volume fetcher — free tier, no auth required."""

import logging

import httpx

from app.core.redis_client import get_json, set_json

logger = logging.getLogger(__name__)

_BASE = "https://api.coingecko.com/api/v3"
_CACHE_KEY = "exchange_volumes"
_TTL = 3600  # 1 hour

# Fallback volumes in BTC (rough order-of-magnitude defaults)
_DEFAULTS: dict[str, float] = {
    "binance": 106_452.0,
    "gdax": 19_197.0,
    "kraken": 15_000.0,
    "okex": 18_000.0,
    "bybit": 22_000.0,
    "huobi": 12_000.0,
    "kucoin": 8_000.0,
    "gemini": 3_500.0,
    "bitfinex": 4_200.0,
    "bitstamp": 2_800.0,
}


async def fetch_exchange_volumes() -> dict[str, float]:
    """Fetch 24h trade volumes (in BTC) for the top 10 exchanges via CoinGecko.

    Returns a dict mapping exchange ID → volume_24h in BTC.
    Results are cached in Redis under ``exchange_volumes`` with a 1-hour TTL.
    Falls back to cached data or hard-coded defaults on any error.
    """
    # Try cache first
    cached = await get_json(_CACHE_KEY)
    if cached and isinstance(cached, dict):
        return cached

    result: dict[str, float] = {}
    try:
        async with httpx.AsyncClient(base_url=_BASE, timeout=20.0) as client:
            r = await client.get("/exchanges", params={"per_page": 10, "page": 1})
            if not r.is_success:
                logger.warning("CoinGecko /exchanges returned %d", r.status_code)
                return dict(_DEFAULTS)

            exchanges = r.json()
            if not isinstance(exchanges, list):
                logger.warning("Unexpected CoinGecko /exchanges response: %r", type(exchanges))
                return dict(_DEFAULTS)

            for ex in exchanges:
                ex_id = ex.get("id", "")
                vol = ex.get("trade_volume_24h_btc")
                if ex_id and vol is not None:
                    try:
                        result[ex_id] = float(vol)
                    except (TypeError, ValueError):
                        pass

    except Exception as exc:
        logger.warning("Exchange volumes fetch error: %s", exc)

    if not result:
        return dict(_DEFAULTS)

    try:
        await set_json(_CACHE_KEY, result, ttl=_TTL)
    except Exception as exc:
        logger.warning("Failed to cache exchange_volumes: %s", exc)

    return result
