from __future__ import annotations

# TODO: Phase 3 — implement Dune Analytics API for community on-chain queries


class DuneClient:
    BASE_URL = "https://api.dune.com/api/v1"

    async def get_dashboard_results(self, dashboard_id: str) -> dict:
        # TODO: Phase 3 — GET /dashboards/{dashboard_id}
        raise NotImplementedError

    async def run_query(self, query_id: int, params: dict | None = None) -> dict:
        # TODO: Phase 3 — POST /query/{query_id}/execute, then GET /execution/{execution_id}/results
        raise NotImplementedError
