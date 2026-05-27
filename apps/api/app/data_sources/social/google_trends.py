from __future__ import annotations

# TODO: Phase 2 — implement Google Trends via pytrends


class GoogleTrendsClient:
    KEYWORDS = ["bitcoin", "ethereum", "crypto crash", "buy bitcoin", "crypto"]

    async def get_interest_over_time(self, keywords: list[str], timeframe: str = "today 3-m") -> dict:
        # TODO: Phase 2 — pytrends TrendReq().build_payload().interest_over_time()
        # Note: pytrends is synchronous — run in executor
        raise NotImplementedError

    async def get_related_queries(self, keyword: str) -> dict:
        # TODO: Phase 2 — pytrends related_queries() for rising/top search terms
        raise NotImplementedError
