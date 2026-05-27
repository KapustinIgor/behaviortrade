from __future__ import annotations

# TODO: Phase 3 — implement The Graph Protocol queries for DeFi on-chain data


class TheGraphClient:
    UNISWAP_V3_SUBGRAPH = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"
    AAVE_V3_SUBGRAPH = "https://api.thegraph.com/subgraphs/name/aave/protocol-v3"

    async def query_uniswap_pools(self, limit: int = 20) -> list[dict]:
        # TODO: Phase 3 — GraphQL query for top pools by TVL
        raise NotImplementedError

    async def query_aave_reserves(self) -> list[dict]:
        # TODO: Phase 3 — GraphQL query for Aave reserve data
        raise NotImplementedError

    async def query_dex_volumes(self, days: int = 7) -> list[dict]:
        # TODO: Phase 3 — aggregate DEX volume across Uniswap, Curve, dYdX
        raise NotImplementedError
