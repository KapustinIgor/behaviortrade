from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.coingecko.com/api/v3"


class CoinGeckoClient:
    def __init__(self) -> None:
        headers = {"accept": "application/json"}
        if settings.COINGECKO_API_KEY:
            headers["x-cg-demo-api-key"] = settings.COINGECKO_API_KEY
        self._client = httpx.AsyncClient(base_url=BASE_URL, headers=headers, timeout=30.0)

    async def _get(self, path: str, params: dict | None = None, retries: int = 4) -> Any:
        delay = 1.0
        for attempt in range(retries):
            try:
                r = await self._client.get(path, params=params)
                if r.status_code == 429:
                    wait = float(r.headers.get("Retry-After", delay * 2))
                    logger.warning("CoinGecko rate limit – waiting %.1fs", wait)
                    await asyncio.sleep(wait)
                    delay = min(delay * 2, 60)
                    continue
                r.raise_for_status()
                return r.json()
            except httpx.HTTPError as e:
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
                logger.warning("CoinGecko request error (attempt %d): %s", attempt + 1, e)
        return {}

    async def get_price(self, assets: list[str]) -> dict[str, Any]:
        ids = ",".join(assets)
        return await self._get(
            "/simple/price",
            params={"ids": ids, "vs_currencies": "usd", "include_24hr_change": "true", "include_24hr_vol": "true"},
        )

    async def get_ohlcv(self, asset: str, days: int = 7) -> list[dict]:
        data = await self._get(f"/coins/{asset}/ohlc", params={"vs_currency": "usd", "days": days})
        if not isinstance(data, list):
            return []
        return [
            {"timestamp": row[0], "open": row[1], "high": row[2], "low": row[3], "close": row[4]}
            for row in data
        ]

    async def get_global_metrics(self) -> dict:
        data = await self._get("/global")
        return data.get("data", {})

    async def get_trending(self) -> list[dict]:
        data = await self._get("/search/trending")
        coins = data.get("coins", [])
        return [c.get("item", {}) for c in coins]

    async def get_market_chart(self, asset: str, days: int = 30) -> dict:
        return await self._get(
            f"/coins/{asset}/market_chart",
            params={"vs_currency": "usd", "days": days, "interval": "daily"},
        )

    async def close(self) -> None:
        await self._client.aclose()
