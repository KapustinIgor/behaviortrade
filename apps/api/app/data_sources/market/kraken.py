from __future__ import annotations

# TODO: Phase 1 extension — implement Kraken REST + WebSocket


class KrakenClient:
    async def get_ohlc(self, pair: str, interval: int = 60) -> list[dict]:
        # TODO: Phase 1 — GET https://api.kraken.com/0/public/OHLC
        raise NotImplementedError

    async def get_ticker(self, pairs: list[str]) -> dict:
        # TODO: Phase 1 — GET https://api.kraken.com/0/public/Ticker
        raise NotImplementedError

    async def subscribe_ticker(self, pairs: list[str], callback) -> None:
        # TODO: Phase 1 — WebSocket wss://ws.kraken.com
        raise NotImplementedError
