from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://blockchain.info"
_WHALE_THRESHOLD_BTC = 10.0


class BlockchainInfoClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(base_url=_BASE, timeout=20.0)

    async def get_large_txs(self, min_btc: float = _WHALE_THRESHOLD_BTC) -> list[dict]:
        """Return recent unconfirmed transactions with total output >= min_btc."""
        try:
            r = await self._client.get("/unconfirmed-transactions", params={"format": "json"})
            if not r.is_success:
                logger.warning("blockchain.info %s", r.status_code)
                return []
            txs = r.json().get("txs", [])
        except httpx.HTTPError as e:
            logger.warning("blockchain.info fetch error: %s", e)
            return []

        result = []
        for tx in txs:
            outputs = tx.get("out", [])
            total_sat = sum(o.get("value", 0) for o in outputs)
            total_btc = total_sat / 1e8
            if total_btc < min_btc:
                continue
            recipients = [o.get("addr", "") for o in outputs if o.get("addr")]
            ts = tx.get("time", 0)
            result.append({
                "hash": tx.get("hash", ""),
                "btc": round(total_btc, 4),
                "fee_sat": tx.get("fee", 0),
                "inputs": tx.get("vin_sz", 0),
                "outputs": tx.get("vout_sz", 0),
                "recipients": recipients[:3],
                "timestamp": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else "",
            })

        result.sort(key=lambda x: x["btc"], reverse=True)
        return result[:20]

    async def get_mempool_stats(self) -> dict:
        try:
            r = await self._client.get("/q/unconfirmedcount")
            count = int(r.text.strip()) if r.is_success else 0
        except Exception:
            count = 0
        return {"unconfirmed_count": count}

    async def close(self) -> None:
        await self._client.aclose()
