from __future__ import annotations

# TODO: Phase 2 — implement Santiment GraphQL API


class SantimentClient:
    GRAPHQL_URL = "https://api.santiment.net/graphql"

    async def get_social_trends(self, asset: str, from_date: str, to_date: str) -> list[dict]:
        # TODO: Phase 2 — GraphQL query socialVolume + socialDominance
        raise NotImplementedError

    async def get_dev_activity(self, asset: str, days: int = 30) -> list[dict]:
        # TODO: Phase 2 — GitHub commit activity as development signal
        raise NotImplementedError
