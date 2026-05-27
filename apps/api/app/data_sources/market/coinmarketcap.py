from __future__ import annotations

# TODO: Phase 3 — implement CoinMarketCap API (requires paid tier for most endpoints)


class CoinMarketCapClient:
    async def get_global_metrics(self) -> dict:
        # TODO: GET https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest
        raise NotImplementedError

    async def get_listings(self, limit: int = 100) -> list[dict]:
        # TODO: GET https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest
        raise NotImplementedError

    async def get_dominance(self) -> dict:
        # TODO: parse BTC/ETH dominance from global metrics
        raise NotImplementedError
