from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.redis_client import get_json, set_json
from app.data_sources.market.coingecko import CoinGeckoClient

router = APIRouter()
_cg = CoinGeckoClient()

ASSET_ID_MAP = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
    "BNB": "binancecoin", "XRP": "ripple", "ADA": "cardano",
    "AVAX": "avalanche-2", "MATIC": "matic-network", "LINK": "chainlink",
    "DOT": "polkadot",
}


@router.get("/{asset}/ohlcv")
async def get_ohlcv(
    asset: str,
    timeframe: str = Query(default="7d"),
    limit: int = Query(default=100, le=1000),
):
    days_map = {"1d": 1, "7d": 7, "30d": 30, "90d": 90, "1y": 365}
    days = days_map.get(timeframe, 7)
    coin_id = ASSET_ID_MAP.get(asset.upper(), asset.lower())
    cache_key = f"ohlcv:{coin_id}:{days}"
    cached = await get_json(cache_key)
    if cached:
        return {"asset": asset, "timeframe": timeframe, "data": cached}
    data = await _cg.get_ohlcv(coin_id, days)
    await set_json(cache_key, data, ttl=300)
    return {"asset": asset, "timeframe": timeframe, "data": data}


@router.get("/{asset}/latest")
async def get_latest_price(asset: str):
    coin_id = ASSET_ID_MAP.get(asset.upper(), asset.lower())
    cached = await get_json(f"price:{coin_id}")
    if cached:
        return cached
    data = await _cg.get_price([coin_id])
    coin_data = data.get(coin_id, {})
    result = {
        "asset": asset,
        "price": coin_data.get("usd", 0),
        "change_24h": coin_data.get("usd_24h_change", 0),
        "volume_24h": coin_data.get("usd_24h_vol", 0),
    }
    await set_json(f"price:{coin_id}", result, ttl=30)
    return result


@router.get("/global")
async def get_global_metrics():
    cached = await get_json("global_metrics")
    if cached:
        return cached
    data = await _cg.get_global_metrics()
    await set_json("global_metrics", data, ttl=300)
    return data
