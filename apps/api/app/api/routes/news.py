from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.redis_client import get_json, get_redis
from app.data_sources.news.cryptopanic import CryptoPanicClient
from app.nlp.finbert import analyze_batch

router = APIRouter()
_cp = CryptoPanicClient()


@router.get("/feed")
async def get_news_feed(
    page: int = Query(default=1, ge=1),
    filter: str = Query(default="hot"),
    currency: str = Query(default=None),
):
    currencies = [currency] if currency else None
    items = await _cp.get_news(currencies=currencies, filter=filter, page=page)
    headlines = [i.get("headline", "") for i in items]
    if headlines:
        sentiments = analyze_batch(headlines)
        for item, sent in zip(items, sentiments):
            item["sentiment_score"] = round(sent["score"], 4)
            item["sentiment_label"] = sent["sentiment"]
    return {"items": items, "page": page}


@router.get("/impact/{headline:path}")
async def get_news_impact(headline: str):
    # TODO: Phase 4 — use NewsImpactAnalyzer to find similar historical headlines
    return {
        "headline": headline,
        "similar_events": [],
        "median_impact_1h": 0.0,
        "median_impact_24h": 0.0,
        "sample_size": 0,
        "note": "Phase 4: news impact analyzer coming soon",
    }


@router.get("/sentiment-heatmap")
async def get_sentiment_heatmap():
    # TODO: Phase 2 — query news_events table grouped by source and day
    return {
        "sources": ["CryptoPanic", "CoinDesk", "CoinTelegraph", "The Block", "Decrypt"],
        "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "data": [],
        "note": "Phase 2: sentiment heatmap coming soon",
    }


@router.websocket("/ws/news")
async def ws_news(websocket: WebSocket):
    await websocket.accept()
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe("news_updates")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        await pubsub.unsubscribe("news_updates")
