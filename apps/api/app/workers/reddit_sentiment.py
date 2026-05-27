from __future__ import annotations

"""
Reddit sentiment pipeline.

Two modes:
  batch_ingest()  — fetches top-N hot posts from each subreddit, scores with FinBERT,
                    stores in Redis + Postgres. Called from periodic refresh (every 10 min).
  stream_loop()   — long-running asyncio task that processes the live comment/post stream.
                    Publishes scored items to the `social_signals` Redis channel in real time.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone

from app.core.redis_client import get_json, get_redis, publish, set_json
from app.data_sources.social.stocktwits import SYMBOLS, StockTwitsClient
from app.nlp.finbert import analyze_batch

logger = logging.getLogger(__name__)

POSTS_KEY      = "reddit_posts_latest"     # list of last 100 scored posts
SENTIMENT_KEY  = "reddit_sentiment_latest" # per-subreddit aggregate
SEEN_SET_KEY   = "reddit_seen_hashes"      # dedup set, TTL 24h
MAX_POSTS      = 100
SEEN_TTL       = 86400


async def _score_posts(posts: list[dict]) -> list[dict]:
    """
    Score posts with FinBERT. StockTwits messages that already have
    a pre-tagged sentiment skip FinBERT and use the tagged value directly.
    """
    if not posts:
        return []
    now = datetime.now(timezone.utc).isoformat()

    # Split: pre-scored (StockTwits Bullish/Bearish tagged) vs needs FinBERT
    needs_nlp = [p for p in posts if not p.get("scored_at") and p.get("sentiment") == "neutral"
                 and p.get("sentiment_score", 0.0) == 0.0]
    pre_scored = [p for p in posts if p not in needs_nlp]

    if needs_nlp:
        texts = [p["text"][:512] for p in needs_nlp]
        sentiments = analyze_batch(texts)
        for post, sent in zip(needs_nlp, sentiments):
            post["sentiment"]       = sent["sentiment"]
            post["sentiment_score"] = round(sent["score"], 4)
            post["positive"]        = round(sent["positive"], 4)
            post["negative"]        = round(sent["negative"], 4)
            post["neutral"]         = round(sent["neutral"], 4)

    for post in posts:
        post["scored_at"] = now
    return posts


async def _dedup(posts: list[dict]) -> list[dict]:
    """Filter posts already seen in the last 24h."""
    r = await get_redis()
    hashes = [p["content_hash"] for p in posts]
    if not hashes:
        return []
    # SMISMEMBER equivalent: check each hash individually
    seen = set()
    for h in hashes:
        if await r.sismember(SEEN_SET_KEY, h):
            seen.add(h)
    fresh = [p for p in posts if p["content_hash"] not in seen]
    if fresh:
        new_hashes = [p["content_hash"] for p in fresh]
        await r.sadd(SEEN_SET_KEY, *new_hashes)
        await r.expire(SEEN_SET_KEY, SEEN_TTL)
    return fresh


def _aggregate(posts: list[dict]) -> dict:
    """Compute per-subreddit sentiment aggregates from a list of scored posts."""
    by_sub: dict[str, list[float]] = {}
    for p in posts:
        sr = p.get("subreddit", "unknown")
        by_sub.setdefault(sr, []).append(p.get("sentiment_score", 0.0))

    agg: dict[str, dict] = {}
    all_scores: list[float] = []
    for sr, scores in by_sub.items():
        mean = sum(scores) / len(scores)
        agg[sr] = {
            "mean_sentiment":  round(mean, 4),
            "post_count":      len(scores),
            "bullish_pct":     round(sum(1 for s in scores if s > 0.1) / len(scores) * 100, 1),
            "bearish_pct":     round(sum(1 for s in scores if s < -0.1) / len(scores) * 100, 1),
        }
        all_scores.extend(scores)

    overall = sum(all_scores) / len(all_scores) if all_scores else 0.0
    return {
        "overall_sentiment": round(overall, 4),
        "total_posts":       len(posts),
        "subreddits":        agg,
        "updated_at":        datetime.now(timezone.utc).isoformat(),
    }


async def _persist_to_db(posts: list[dict]) -> None:
    """Write scored posts to the social_signals Postgres table."""
    if not posts:
        return
    try:
        from sqlalchemy import insert
        from app.core.database import AsyncSessionLocal
        from app.models.social import SocialSignal

        records = []
        for p in posts:
            ts = datetime.fromtimestamp(p.get("created_utc", time.time()), tz=timezone.utc)
            records.append({
                "platform":         "reddit",
                "content_hash":     p["content_hash"],
                "sentiment":        p.get("sentiment_score", 0.0),
                "influence_weight": max(1.0, (p.get("score", 0) / 100.0) + 1.0),
                "timestamp":        ts,
                "asset_mentions":   p.get("asset_mentions", []),
                "raw_text":         p["text"][:2000],
            })

        async with AsyncSessionLocal() as session:
            # INSERT OR IGNORE via on_conflict_do_nothing
            stmt = insert(SocialSignal).values(records).prefix_with("OR IGNORE")
            # For Postgres use on_conflict_do_nothing
            try:
                from sqlalchemy.dialects.postgresql import insert as pg_insert
                stmt = pg_insert(SocialSignal).values(records).on_conflict_do_nothing(
                    index_elements=["content_hash"]
                )
            except Exception:
                pass
            await session.execute(stmt)
            await session.commit()
    except Exception as e:
        logger.warning("DB persist failed: %s", e)


# ── Public API ────────────────────────────────────────────────────────────────

async def batch_ingest(limit_per_sub: int = 30) -> dict:
    """Fetch StockTwits messages, score, store in Redis + DB. Returns aggregate."""
    client = StockTwitsClient()
    raw = await client.get_messages_all(limit_per_symbol=limit_per_sub)

    fresh = await _dedup(raw)
    if not fresh:
        logger.info("Reddit batch: all %d posts already seen", len(raw))
        cached = await get_json(SENTIMENT_KEY)
        return cached or {}

    scored = await _score_posts(fresh)
    asyncio.create_task(_persist_to_db(scored))

    # Merge with existing posts in Redis (keep latest MAX_POSTS)
    r = await get_redis()
    for post in scored:
        await r.lpush(POSTS_KEY, json.dumps(post))
    await r.ltrim(POSTS_KEY, 0, MAX_POSTS - 1)
    await r.expire(POSTS_KEY, 3600)

    agg = _aggregate(scored)
    await set_json(SENTIMENT_KEY, agg, ttl=600)
    await publish("social_signals", {"type": "reddit_batch", **agg})

    logger.info(
        "Reddit batch: %d new posts scored  overall=%.3f",
        len(scored), agg.get("overall_sentiment", 0),
    )
    return agg


async def stream_loop() -> None:
    """Polling loop: re-fetches hot posts every 5 min, publishes new ones in real time."""
    logger.info("Reddit poll_loop starting (public JSON, no credentials needed)")
    POLL_INTERVAL = 300  # 5 min — well within public rate limits

    while True:
        try:
            agg = await batch_ingest(limit_per_sub=25)
            if agg:
                logger.debug("Reddit poll: overall=%.3f", agg.get("overall_sentiment", 0))
        except asyncio.CancelledError:
            logger.info("Reddit poll_loop cancelled")
            return
        except Exception as e:
            logger.warning("Reddit poll_loop error: %s", e)
        await asyncio.sleep(POLL_INTERVAL)
