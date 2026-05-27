from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.glassnode.com/v1/metrics"


class GlassnodeClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(base_url=BASE_URL, timeout=30.0)
        self._key = settings.GLASSNODE_API_KEY

    async def _get(self, path: str, params: dict | None = None) -> list | dict:
        p = {"a": "BTC", "api_key": self._key, **(params or {})}
        try:
            r = await self._client.get(path, params=p)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as e:
            logger.warning("Glassnode error %s: %s", path, e)
            return []

    async def get_sopr(self, asset: str = "BTC") -> list[dict]:
        # TODO: Phase 2 — parse SOPR metric (Spent Output Profit Ratio)
        return await self._get("/indicators/sopr", {"a": asset})  # type: ignore

    async def get_mvrv(self, asset: str = "BTC") -> list[dict]:
        # TODO: Phase 2 — Market Value to Realized Value ratio
        return await self._get("/market/mvrv", {"a": asset})  # type: ignore

    async def get_exchange_reserves(self, asset: str = "BTC") -> list[dict]:
        # TODO: Phase 2 — total coins on exchanges
        return await self._get("/distribution/balance_exchanges", {"a": asset})  # type: ignore

    async def get_whale_movements(self, asset: str = "BTC") -> list[dict]:
        # TODO: Phase 2 — large transaction count (> 1000 BTC)
        return await self._get("/transactions/transfers_volume_large", {"a": asset})  # type: ignore

    async def close(self) -> None:
        await self._client.aclose()
