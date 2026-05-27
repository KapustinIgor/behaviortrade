from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis_client import get_json, get_redis, set_json
from app.gnn.inference import GNNInference
from app.models.behavioral import BehavioralScore

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
    db: AsyncSession = Depends(get_db),
):
    """
    Returns behavioral score history from the DB (rows written by the periodic
    refresh loop) plus a synthetic series generated from Redis price/F&G data.
    """
    # ── Parse time range ──────────────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    try:
        dt_from = datetime.fromisoformat(from_ts) if from_ts else now - timedelta(hours=168)
        dt_to   = datetime.fromisoformat(to_ts)   if to_ts   else now
    except ValueError:
        dt_from = now - timedelta(hours=168)
        dt_to   = now

    # ── Try DB first ──────────────────────────────────────────────────────────
    try:
        stmt = (
            select(BehavioralScore)
            .where(BehavioralScore.timestamp >= dt_from)
            .where(BehavioralScore.timestamp <= dt_to)
            .order_by(BehavioralScore.timestamp.desc())
            .limit(limit)
        )
        rows = (await db.execute(stmt)).scalars().all()
        if rows:
            data = [
                {
                    "timestamp":          r.timestamp.isoformat(),
                    "panic_score":        r.panic_score,
                    "greed_score":        r.greed_score,
                    "accumulation_score": r.accumulation_score,
                    "distribution_score": r.distribution_score,
                    "regime":             r.regime,
                    "confidence":         r.confidence,
                }
                for r in reversed(rows)
            ]
            return {"asset": asset, "data": data, "source": "db"}
    except Exception:
        pass

    # ── Fallback: synthesise history from price series + current scores ───────
    try:
        from app.strategies.signal_engine import fetch_price_history
        coin_map = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
                    "BNB": "binancecoin", "XRP": "ripple"}
        history = await fetch_price_history(coin_map.get(asset.upper(), "bitcoin"), hours=min(limit, 168))
        current = await get_json("behavioral_scores_latest") or {}
        fg_data = await get_json("fear_greed_latest") or {}
        fg_val  = float(fg_data.get("value", 50)) / 100.0

        data = []
        prices = [h["price"] for h in history]
        for i, h in enumerate(history):
            ctx   = prices[:i + 1]
            if len(ctx) < 2:
                continue
            ch1  = (ctx[-1] - ctx[-2]) / ctx[-2] if ctx[-2] > 0 else 0.0
            ch24 = (ctx[-1] - ctx[max(0, len(ctx)-25)]) / ctx[max(0, len(ctx)-25)] if len(ctx) > 1 else 0.0
            greed = min(100.0, max(0.0, 50 + ch24 * 500))
            panic = min(100.0, max(0.0, 50 - ch24 * 500))
            data.append({
                "timestamp":          datetime.fromtimestamp(h["ts"], tz=timezone.utc).isoformat(),
                "panic_score":        round(panic, 1),
                "greed_score":        round(greed, 1),
                "accumulation_score": round(50 + ch1 * 200, 1),
                "distribution_score": round(50 - ch1 * 200, 1),
                "regime":             current.get("regime", "sideways"),
                "confidence":         round(current.get("confidence", 50), 1),
            })
        return {"asset": asset, "data": data[-limit:], "source": "derived"}
    except Exception:
        return {"asset": asset, "data": [], "source": "unavailable"}


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
