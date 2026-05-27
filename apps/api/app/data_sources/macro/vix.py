from __future__ import annotations

# TODO: Phase 3 — implement VIX (CBOE Volatility Index) as traditional market fear gauge


class VIXClient:
    async def get_vix(self, period: str = "1mo") -> list[dict]:
        # TODO: Phase 3 — yfinance.Ticker("^VIX").history(period=period) — run in executor
        raise NotImplementedError

    async def get_current_vix(self) -> float:
        # TODO: Phase 3 — get latest VIX value
        raise NotImplementedError
