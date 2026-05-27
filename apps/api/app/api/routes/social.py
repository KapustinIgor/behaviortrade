from __future__ import annotations

import json

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.redis_client import get_json, get_redis
from app.workers.reddit_sentiment import POSTS_KEY, SENTIMENT_KEY

router = APIRouter()


@router.get("/reddit/sentiment")
async def get_reddit_sentiment():
    """Aggregated sentiment per subreddit, updated every 10 min."""
    data = await get_json(SENTIMENT_KEY)
    if data:
        return data
    return {
        "overall_sentiment": 0.0,
        "total_posts": 0,
        "subreddits": {},
        "updated_at": None,
        "note": "Reddit credentials not yet configured or first fetch pending",
    }


@router.get("/reddit/posts")
async def get_reddit_posts(limit: int = Query(default=20, le=100)):
    """Latest scored Reddit posts."""
    r = await get_redis()
    raw = await r.lrange(POSTS_KEY, 0, limit - 1)
    posts = []
    for item in raw:
        try:
            posts.append(json.loads(item))
        except Exception:
            pass
    return {"posts": posts, "count": len(posts)}


@router.get("/reddit/posts/{subreddit}")
async def get_reddit_posts_by_sub(subreddit: str, limit: int = Query(default=20, le=50)):
    r = await get_redis()
    raw = await r.lrange(POSTS_KEY, 0, 99)
    posts = []
    for item in raw:
        try:
            p = json.loads(item)
            if p.get("subreddit", "").lower() == subreddit.lower():
                posts.append(p)
        except Exception:
            pass
    return {"subreddit": subreddit, "posts": posts[:limit], "count": len(posts[:limit])}


@router.websocket("/ws/social")
async def ws_social(websocket: WebSocket):
    """Real-time Reddit stream — emits scored posts as they arrive."""
    await websocket.accept()
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe("social_signals")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        await pubsub.unsubscribe("social_signals")
