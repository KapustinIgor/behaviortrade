from __future__ import annotations

# TODO: Phase 2 — implement CryptoQuant exchange flow data


class CryptoQuantClient:
    async def get_exchange_inflows(self, asset: str = "btc", exchange: str = "all_exchange") -> list[dict]:
        # TODO: Phase 2 — GET https://api.cryptoquant.com/v1/{asset}/exchange-flows/inflow
        raise NotImplementedError

    async def get_exchange_outflows(self, asset: str = "btc", exchange: str = "all_exchange") -> list[dict]:
        # TODO: Phase 2 — GET https://api.cryptoquant.com/v1/{asset}/exchange-flows/outflow
        raise NotImplementedError

    async def get_miner_flows(self, asset: str = "btc") -> list[dict]:
        # TODO: Phase 2 — GET https://api.cryptoquant.com/v1/{asset}/miner-flows/inflow-top10
        raise NotImplementedError

    async def get_fund_flows(self, asset: str = "btc") -> list[dict]:
        # TODO: Phase 2 — GET https://api.cryptoquant.com/v1/{asset}/fund-flows/inflow
        raise NotImplementedError
