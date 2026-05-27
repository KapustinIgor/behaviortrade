from __future__ import annotations

# TODO: Phase 4 — implement Kaiko institutional tick data (freemium)


class KaikoClient:
    async def get_trades(self, exchange: str, instrument_class: str, code: str) -> list[dict]:
        # TODO: GET https://us.market-api.kaiko.io/v2/data/trades.v1/exchanges/{exchange}/{class}/{code}/trades
        raise NotImplementedError

    async def get_order_book_snapshots(self, exchange: str, code: str) -> list[dict]:
        # TODO: GET Kaiko order book snapshot endpoint
        raise NotImplementedError
