from __future__ import annotations

# TODO: Phase 2 — implement Etherscan API for Ethereum on-chain data


class EtherscanClient:
    async def get_wallet_balance(self, address: str) -> float:
        # TODO: Phase 2 — GET https://api.etherscan.io/api?module=account&action=balance
        raise NotImplementedError

    async def get_token_transfers(self, address: str, contract: str | None = None) -> list[dict]:
        # TODO: Phase 2 — GET module=account&action=tokentx
        raise NotImplementedError

    async def get_contract_events(self, address: str, from_block: int = 0) -> list[dict]:
        # TODO: Phase 2 — GET module=logs&action=getLogs
        raise NotImplementedError

    async def get_gas_oracle(self) -> dict:
        # TODO: Phase 2 — GET module=gastracker&action=gasoracle
        raise NotImplementedError
