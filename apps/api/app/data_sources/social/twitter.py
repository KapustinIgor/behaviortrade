from __future__ import annotations

# TODO: Phase 2 — implement Twitter/X v2 API (free tier: 500k tweets/month)


class TwitterClient:
    BASE_URL = "https://api.twitter.com/2"

    async def stream_keywords(self, keywords: list[str], callback) -> None:
        # TODO: Phase 2 — filtered stream endpoint with rules for BTC, ETH, crypto, etc.
        raise NotImplementedError

    async def get_recent_tweets(self, query: str, max_results: int = 100) -> list[dict]:
        # TODO: Phase 2 — GET /tweets/search/recent
        raise NotImplementedError

    async def get_user_timeline(self, user_id: str, max_results: int = 100) -> list[dict]:
        # TODO: Phase 2 — GET /users/{id}/tweets
        raise NotImplementedError
