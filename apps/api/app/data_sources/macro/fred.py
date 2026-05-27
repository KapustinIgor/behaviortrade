from __future__ import annotations

# TODO: Phase 3 — implement FRED API for macro correlating data


class FREDClient:
    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    async def get_fed_rate(self) -> list[dict]:
        # TODO: Phase 3 — series_id=FEDFUNDS
        raise NotImplementedError

    async def get_cpi(self) -> list[dict]:
        # TODO: Phase 3 — series_id=CPIAUCSL
        raise NotImplementedError

    async def get_m2_supply(self) -> list[dict]:
        # TODO: Phase 3 — series_id=M2SL
        raise NotImplementedError
