from __future__ import annotations

# TODO: Phase 3 — implement Nansen smart money wallet labels


class NansenClient:
    async def get_smart_money_flows(self, asset: str, days: int = 7) -> list[dict]:
        # TODO: Phase 3 — Nansen API smart money net flow
        raise NotImplementedError

    async def get_wallet_labels(self, address: str) -> list[str]:
        # TODO: Phase 3 — GET wallet entity labels from Nansen
        raise NotImplementedError
