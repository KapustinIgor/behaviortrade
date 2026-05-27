from __future__ import annotations

# TODO: Phase 2 — implement LunarCrush API for social volume metrics


class LunarCrushClient:
    BASE_URL = "https://lunarcrush.com/api4/public"

    async def get_social_volume(self, asset: str) -> dict:
        # TODO: Phase 2 — GET /coins/{asset}/v1 — social_volume_24h
        raise NotImplementedError

    async def get_social_dominance(self, asset: str) -> float:
        # TODO: Phase 2 — social_dominance field from coin metrics
        raise NotImplementedError

    async def get_galaxy_score(self, asset: str) -> float:
        # TODO: Phase 2 — LunarCrush Galaxy Score (composite social health metric)
        raise NotImplementedError
