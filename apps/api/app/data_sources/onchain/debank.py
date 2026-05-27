from __future__ import annotations

# TODO: Phase 3 — implement DeBank API for multi-chain DeFi portfolio data


class DeBankClient:
    async def get_portfolio(self, address: str) -> dict:
        # TODO: Phase 3 — GET https://pro-openapi.debank.com/v1/user/total_balance
        raise NotImplementedError

    async def get_protocol_tvl(self, protocol_id: str) -> dict:
        # TODO: Phase 3 — GET https://pro-openapi.debank.com/v1/protocol?id={protocol_id}
        raise NotImplementedError
