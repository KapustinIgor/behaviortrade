from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.redis_client import get_json, get_redis, set_json
from app.gnn.inference import GNNInference

router = APIRouter()


def _get_gnn() -> GNNInference:
    from app.main import _gnn_inference
    return _gnn_inference or GNNInference()


@router.get("/scores")
async def get_behavioral_scores():
    cached = await get_json("behavioral_scores_latest")
    if cached:
        return cached
    scores = await _get_gnn().get_behavioral_scores()
    await set_json("behavioral_scores_latest", scores, ttl=120)
    return scores


@router.get("/scores/{asset}")
async def get_asset_behavioral_scores(asset: str):
    scores = await _get_gnn().get_behavioral_scores()
    scores["asset"] = asset
    return scores


@router.get("/fear-greed")
async def get_fear_greed():
    cached = await get_json("fear_greed_latest")
    if cached:
        return cached
    from app.data_sources.social.fear_greed import get_fear_greed as _fetch
    data = await _fetch(limit=30)
    await set_json("fear_greed_latest", data, ttl=7200)
    return data


@router.get("/whale-flows")
async def get_whale_flows(min_btc: float = Query(default=10.0, ge=1.0)):
    cache_key = f"whale_flows:{int(min_btc)}"
    cached = await get_json(cache_key)
    if cached:
        return {"flows": cached, "min_btc": min_btc, "source": "blockchain.info"}
    from app.data_sources.onchain.blockchain_info import BlockchainInfoClient
    client = BlockchainInfoClient()
    try:
        flows = await client.get_large_txs(min_btc=min_btc)
    finally:
        await client.close()
    await set_json(cache_key, flows, ttl=60)
    return {"flows": flows, "min_btc": min_btc, "source": "blockchain.info"}


@router.get("/history")
async def get_behavioral_history(
    asset: str = Query(default="BTC"),
    from_ts: str = Query(default=None, alias="from"),
    to_ts: str = Query(default=None, alias="to"),
    limit: int = Query(default=100, le=500),
):
    # TODO: Phase 2 — query behavioral_scores table filtered by asset + time range
    return {"asset": asset, "data": [], "note": "Phase 2: historical behavioral data coming soon"}


@router.websocket("/ws/behavioral")
async def ws_behavioral(websocket: WebSocket):
    await websocket.accept()
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe("behavioral_scores")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        await pubsub.unsubscribe("behavioral_scores")
