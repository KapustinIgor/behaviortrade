from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://data-api.cryptocompare.com"


class CryptoPanicClient:
    """News client backed by CryptoCompare data-api (free, no auth required)."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(base_url=BASE_URL, timeout=20.0)

    async def get_news(
        self,
        currencies: list[str] | None = None,
        filter: str = "hot",
        page: int = 1,
    ) -> list[dict]:
        params: dict = {"limit": 20, "lang": "EN"}
        if currencies:
            params["categories"] = ",".join(currencies)

        try:
            r = await self._client.get("/news/v1/article/list", params=params)
            if not r.is_success:
                logger.warning("CryptoCompare news %s: %s", r.status_code, r.text[:200])
                return []
            data = r.json()
        except httpx.HTTPError as e:
            logger.warning("CryptoCompare news fetch error: %s", e)
            return []

        items = data.get("Data", [])
        logger.info("CryptoCompare news returned %d items", len(items))
        return [self._normalize(item) for item in items]

    async def get_breaking_news(self) -> list[dict]:
        return await self.get_news()

    @staticmethod
    def _normalize(item: dict) -> dict:
        source = item.get("SOURCE_DATA") or {}
        ts = item.get("PUBLISHED_ON", 0)
        published_at = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else ""
        categories = item.get("CATEGORY_DATA") or []
        # Only keep entries that look like coin tickers (1-6 uppercase letters, no spaces)
        currencies = [
            c["NAME"] for c in categories
            if c.get("NAME") and c["NAME"].isupper() and len(c["NAME"]) <= 6 and " " not in c["NAME"]
        ]
        sentiment = (item.get("SENTIMENT") or "").lower()
        return {
            "id": item.get("ID"),
            "source": source.get("NAME", "Unknown"),
            "source_domain": source.get("SOURCE_KEY", ""),
            "headline": item.get("TITLE", ""),
            "url": item.get("URL", ""),
            "published_at": published_at,
            "currencies": currencies,
            "votes": {
                "positive": item.get("UPVOTES", 0),
                "negative": item.get("DOWNVOTES", 0),
            },
            "kind": "news",
            "sentiment": sentiment,
        }

    async def close(self) -> None:
        await self._client.aclose()
