from __future__ import annotations

# TODO: Phase 1 extension — implement Coinbase Advanced Trade API


class CoinbaseClient:
    async def get_best_bid_ask(self, product_ids: list[str]) -> dict:
        # TODO: Phase 1 — GET /api/v3/brokerage/best_bid_ask
        raise NotImplementedError

    async def get_candles(self, product_id: str, granularity: str, start: str, end: str) -> list[dict]:
        # TODO: Phase 1 — GET /api/v3/brokerage/products/{product_id}/candles
        raise NotImplementedError

    async def subscribe_ticker(self, product_ids: list[str], callback) -> None:
        # TODO: Phase 1 — WebSocket wss://advanced-trade-ws.coinbase.com
        raise NotImplementedError
