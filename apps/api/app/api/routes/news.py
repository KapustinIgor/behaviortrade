from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.redis_client import get_json, get_redis, set_json
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
    # Cache latest for heatmap use
    if page == 1:
        await set_json("news_latest", items[:30], ttl=600)
    return {"items": items, "page": page}


@router.get("/latest")
async def get_news_latest(limit: int = Query(default=20, le=50)):
    """Alias that returns cached news — used by the copilot context builder."""
    cached = await get_json("news_latest") or []
    return cached[:limit]


@router.get("/impact/{headline:path}")
async def get_news_impact(headline: str):
    """
    Find similar past headlines in Redis cache and estimate price impact.
    Full ML-based analyzer is Phase 4; this version uses keyword + sentiment matching.
    """
    cached = await get_json("news_latest") or []
    if not cached:
        return {
            "headline": headline,
            "similar_events": [],
            "median_impact_1h": 0.0,
            "median_impact_24h": 0.0,
            "sample_size": 0,
        }

    # Simple keyword overlap scoring
    query_words = set(headline.lower().split())
    scored = []
    for item in cached:
        item_words = set(item.get("headline", "").lower().split())
        overlap = len(query_words & item_words) / max(len(query_words), 1)
        if overlap > 0.2:
            scored.append({
                "headline":       item.get("headline", ""),
                "similarity":     round(overlap, 2),
                "sentiment":      item.get("sentiment_label", "neutral"),
                "sentiment_score": item.get("sentiment_score", 0.0),
                "published_at":   item.get("published_at", ""),
            })

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    sentiments = [s["sentiment_score"] for s in scored[:10]]
    median_sentiment = sorted(sentiments)[len(sentiments) // 2] if sentiments else 0.0

    return {
        "headline":          headline,
        "similar_events":    scored[:5],
        "median_sentiment":  round(median_sentiment, 3),
        "median_impact_1h":  round(median_sentiment * 2.5, 2),   # heuristic: ±2.5% per unit sentiment
        "median_impact_24h": round(median_sentiment * 5.0, 2),
        "sample_size":       len(scored),
    }


@router.get("/sentiment-heatmap")
async def get_sentiment_heatmap():
    """
    Builds a source × day-of-week sentiment heatmap from the cached news items.
    Each cell is the average sentiment_score for articles from that source on that day.
    """
    cached = await get_json("news_latest") or []
    if not cached:
        return {"sources": [], "days": [], "data": []}

    DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    sources_set: set[str] = set()
    # bucket[source][day_idx] = list of scores
    bucket: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))

    for item in cached:
        src   = item.get("source", "Unknown")
        score = float(item.get("sentiment_score", 0.0))
        pub   = item.get("published_at", "")
        try:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            day_idx = dt.weekday()  # 0=Mon … 6=Sun
        except Exception:
            day_idx = datetime.now(timezone.utc).weekday()
        sources_set.add(src)
        bucket[src][day_idx].append(score)

    sources = sorted(sources_set)
    data: list[list[float]] = []
    for src in sources:
        row = []
        for d in range(7):
            vals = bucket[src].get(d, [])
            row.append(round(sum(vals) / len(vals), 3) if vals else 0.0)
        data.append(row)

    return {
        "sources": sources,
        "days":    DAY_NAMES,
        "data":    data,
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
