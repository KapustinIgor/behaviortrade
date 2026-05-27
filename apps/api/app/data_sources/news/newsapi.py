from __future__ import annotations

# TODO: Phase 2 — implement NewsAPI.org for general crypto news headlines


class NewsAPIClient:
    BASE_URL = "https://newsapi.org/v2"

    async def get_crypto_headlines(self, page_size: int = 100) -> list[dict]:
        # TODO: Phase 2 — GET /everything?q=crypto+bitcoin&language=en&sortBy=publishedAt
        raise NotImplementedError

    async def search_articles(self, query: str, from_date: str | None = None) -> list[dict]:
        # TODO: Phase 2 — GET /everything?q={query}
        raise NotImplementedError
