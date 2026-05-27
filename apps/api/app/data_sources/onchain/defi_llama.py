from __future__ import annotations

"""DeFiLlama TVL fetcher — free, no auth required."""

import logging

import httpx

from app.core.redis_client import get_json, set_json

logger = logging.getLogger(__name__)

_BASE = "https://api.llama.fi"
_PROTOCOLS = ["uniswap-v3", "aave-v3", "curve-dex", "compound-v3", "dydx"]
_CACHE_KEY = "defi_tvl"
_TTL = 3600

_DEFAULTS: dict[str, float] = {
    "uniswap-v3": 1_740_000_000.0,
    "aave-v3": 14_100_000_000.0,
    "curve-dex": 1_660_000_000.0,
    "compound-v3": 1_220_000_000.0,
    "dydx": 140_000_000.0,
}


async def fetch_defi_tvl() -> dict[str, float]:
    """Fetch current TVL for each DeFi protocol from DeFiLlama.

    Returns a dict mapping protocol slug → TVL in USD.
    Results are cached in Redis under ``defi_tvl`` with a 1-hour TTL.
    Falls back to cached data or hard-coded defaults on any error.
    """
    # Try cache first
    cached = await get_json(_CACHE_KEY)
    if cached and isinstance(cached, dict):
        return cached

    result: dict[str, float] = {}
    async with httpx.AsyncClient(base_url=_BASE, timeout=15.0) as client:
        for slug in _PROTOCOLS:
            try:
                r = await client.get(f"/tvl/{slug}")
                if r.is_success:
                    value = r.json()
                    if isinstance(value, (int, float)):
                        result[slug] = float(value)
                    else:
                        logger.warning("Unexpected TVL response for %s: %r", slug, value)
                        result[slug] = _DEFAULTS[slug]
                else:
                    logger.warning("DeFiLlama %s returned %d", slug, r.status_code)
                    result[slug] = _DEFAULTS[slug]
            except Exception as exc:
                logger.warning("DeFiLlama fetch error for %s: %s", slug, exc)
                result[slug] = _DEFAULTS[slug]

    if result:
        try:
            await set_json(_CACHE_KEY, result, ttl=_TTL)
        except Exception as exc:
            logger.warning("Failed to cache defi_tvl: %s", exc)

    return result or dict(_DEFAULTS)
