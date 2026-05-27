from __future__ import annotations

# TODO: Phase 3 — implement Yahoo Finance cross-asset correlation data via yfinance


class YahooFinanceClient:
    async def get_spy(self, period: str = "1mo") -> list[dict]:
        # TODO: Phase 3 — yfinance.Ticker("SPY").history(period=period) — run in executor
        raise NotImplementedError

    async def get_dxy(self, period: str = "1mo") -> list[dict]:
        # TODO: Phase 3 — yfinance.Ticker("DX-Y.NYB").history(period=period)
        raise NotImplementedError

    async def get_gold(self, period: str = "1mo") -> list[dict]:
        # TODO: Phase 3 — yfinance.Ticker("GC=F").history(period=period)
        raise NotImplementedError

    async def get_qqq(self, period: str = "1mo") -> list[dict]:
        # TODO: Phase 3 — yfinance.Ticker("QQQ").history(period=period)
        raise NotImplementedError
