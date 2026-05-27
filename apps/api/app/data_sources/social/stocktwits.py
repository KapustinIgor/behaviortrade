from __future__ import annotations

"""
StockTwits client — public API, no credentials required.

Fetches recent messages for crypto symbols and normalises them into the
same shape as Reddit posts so the rest of the pipeline is unchanged.
"""

import asyncio
import hashlib
import json
import logging
import time
import urllib.request

logger = logging.getLogger(__name__)

SYMBOLS: dict[str, str] = {
    "BTC": "BTC.X",
    "ETH": "ETH.X",
    "SOL": "SOL.X",
    "BNB": "BNB.X",
    "XRP": "XRP.X",
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BehaviorTrade/0.1)",
    "Accept": "application/json",
}

_SENT_SCORE = {"Bullish": 0.6, "Bearish": -0.6, None: 0.0}
_SENT_LABEL = {"Bullish": "positive", "Bearish": "negative", None: "neutral"}


def _fetch_symbol_sync(st_symbol: str, limit: int) -> list[dict]:
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{st_symbol}.json?limit={min(limit, 30)}"
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        logger.warning("%s fetch failed: %s", st_symbol, e)
        return []

    ticker = st_symbol.replace(".X", "")
    posts: list[dict] = []
    for msg in data.get("messages", []):
        body = (msg.get("body") or "").strip()
        if len(body) < 5:
            continue
        sent_raw   = (msg.get("entities") or {}).get("sentiment") or {}
        sent_basic = sent_raw.get("basic")  # "Bullish" | "Bearish" | None
        score      = _SENT_SCORE.get(sent_basic, 0.0)
        label      = _SENT_LABEL.get(sent_basic, "neutral")
        likes      = msg.get("likes") or {}
        like_count = likes.get("total", 0) if isinstance(likes, dict) else 0

        posts.append({
            "platform":        "stocktwits",
            "kind":            "message",
            "id":              str(msg.get("id", "")),
            "text":            body[:500],
            "title":           body[:120],
            "score":           like_count,
            "upvote_ratio":    0.5,
            "num_comments":    0,
            "created_utc":     time.time(),
            "subreddit":       ticker,
            "url":             f"https://stocktwits.com/{(msg.get('user') or {}).get('username', '')}",
            "content_hash":    hashlib.sha256(body[:256].encode()).hexdigest()[:16],
            "asset_mentions":  [ticker],
            "sentiment":       label,
            "sentiment_score": score,
            "positive":        max(0.0, score),
            "negative":        max(0.0, -score),
            "neutral":         0.0 if sent_basic else 1.0,
        })
    return posts


class StockTwitsClient:
    def is_configured(self) -> bool:
        return True

    async def get_messages(self, st_symbol: str, limit: int = 30) -> list[dict]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _fetch_symbol_sync, st_symbol, limit)

    async def get_messages_all(self, limit_per_symbol: int = 20) -> list[dict]:
        all_posts: list[dict] = []
        for ticker, st_symbol in SYMBOLS.items():
            posts = await self.get_messages(st_symbol, limit=limit_per_symbol)
            all_posts.extend(posts)
            logger.debug("%s: %d messages", st_symbol, len(posts))
            await asyncio.sleep(0.3)
        return all_posts
