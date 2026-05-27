from __future__ import annotations

# TODO: Phase 4 — implement SEC EDGAR API for regulatory filings mentioning crypto


class SECEdgarClient:
    BASE_URL = "https://efts.sec.gov/LATEST/search-index"

    async def search_filings(self, query: str, date_range: str = "custom", start_dt: str = "", end_dt: str = "") -> list[dict]:
        # TODO: Phase 4 — GET https://efts.sec.gov/LATEST/search-index?q={query}&dateRange=custom
        raise NotImplementedError

    async def get_crypto_mentions(self, days: int = 7) -> list[dict]:
        # TODO: Phase 4 — search for "bitcoin", "cryptocurrency", "digital asset" in recent filings
        raise NotImplementedError
