from __future__ import annotations

# TODO: Phase 3 — implement Messari API for research-grade asset fundamentals


class MessariClient:
    async def get_asset_metrics(self, asset: str) -> dict:
        # TODO: GET https://data.messari.io/api/v1/assets/{asset}/metrics
        raise NotImplementedError

    async def get_asset_profile(self, asset: str) -> dict:
        # TODO: GET https://data.messari.io/api/v2/assets/{asset}/profile
        raise NotImplementedError

    async def get_news(self) -> list[dict]:
        # TODO: GET https://data.messari.io/api/v1/news
        raise NotImplementedError
