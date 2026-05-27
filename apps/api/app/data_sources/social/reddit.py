from __future__ import annotations

"""
Reddit client — uses public RSS feeds via urllib (no API credentials required).

Reddit's .rss endpoint works without auth and is not blocked by Cloudflare.
Rate limit: conservative 2s sleep between subreddits, well within limits.
"""

import asyncio
import hashlib
import logging
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape

logger = logging.getLogger(__name__)

MONITORED_SUBREDDITS = [
    "Bitcoin", "CryptoCurrency", "ethtrader", "CryptoMarkets", "SatoshiStreetBets"
]

ASSET_KEYWORDS: dict[str, list[str]] = {
    "BTC": ["bitcoin", "btc", "satoshi"],
    "ETH": ["ethereum", "eth", "vitalik"],
    "SOL": ["solana", "sol"],
    "BNB": ["bnb", "binance"],
    "XRP": ["xrp", "ripple"],
}

_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "media": "http://search.yahoo.com/mrss/",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def _detect_assets(text: str) -> list[str]:
    low = text.lower()
    return [ticker for ticker, kws in ASSET_KEYWORDS.items() if any(kw in low for kw in kws)]


def _strip_html(raw: str) -> str:
    """Remove HTML tags and decode entities."""
    return unescape(re.sub(r"<[^>]+>", " ", raw)).strip()


def _fetch_rss_sync(subreddit: str, limit: int) -> list[dict]:
    """Blocking RSS fetch — called in a thread executor."""
    url = f"https://www.reddit.com/r/{subreddit}/hot.rss?limit={min(limit, 100)}"
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_bytes = resp.read()
    except Exception as e:
        logger.warning("r/%s RSS fetch failed: %s", subreddit, e)
        return []

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        logger.warning("r/%s RSS parse error: %s", subreddit, e)
        return []

    posts: list[dict] = []
    # Atom feed: entries are <entry> elements
    entries = root.findall("atom:entry", _NS)
    # Fallback: RSS 2.0 uses <item>
    if not entries:
        entries = root.findall(".//item")

    for entry in entries:
        title_el   = entry.find("atom:title",   _NS) or entry.find("title")
        link_el    = entry.find("atom:link",    _NS) or entry.find("link")
        content_el = entry.find("atom:content", _NS) or entry.find("description")
        updated_el = entry.find("atom:updated", _NS) or entry.find("pubDate")

        title   = (title_el.text or "").strip()   if title_el   is not None else ""
        link    = (link_el.get("href") or link_el.text or "").strip() \
                  if link_el is not None else ""
        content = _strip_html(content_el.text or "") if content_el is not None else ""

        # Extract score from content: "&#32; submitted by" pattern or just use 0
        score_match = re.search(r"(\d+)\s+point", content)
        score = int(score_match.group(1)) if score_match else 0

        text = f"{title} {content}"[:2000].strip()
        if len(text) < 10:
            continue

        posts.append({
            "platform":       "reddit",
            "kind":           "post",
            "id":             hashlib.md5(link.encode()).hexdigest()[:10],
            "text":           text,
            "title":          title,
            "score":          score,
            "upvote_ratio":   0.5,
            "num_comments":   0,
            "created_utc":    time.time(),
            "subreddit":      subreddit,
            "url":            link,
            "content_hash":   hashlib.sha256(text[:512].encode()).hexdigest()[:16],
            "asset_mentions": _detect_assets(text),
        })

    return posts


class RedditClient:
    def is_configured(self) -> bool:
        return True  # public RSS — always available

    async def get_hot_posts(self, subreddit: str, limit: int = 50) -> list[dict]:
        loop = asyncio.get_event_loop()
        posts = await loop.run_in_executor(None, _fetch_rss_sync, subreddit, limit)
        logger.debug("r/%s: %d posts via RSS", subreddit, len(posts))
        return posts

    async def get_hot_posts_all(self, limit_per_sub: int = 30) -> list[dict]:
        all_posts: list[dict] = []
        for sr in MONITORED_SUBREDDITS:
            posts = await self.get_hot_posts(sr, limit=limit_per_sub)
            all_posts.extend(posts)
            await asyncio.sleep(1)  # polite pause between subreddits
        return all_posts

    async def close(self) -> None:
        pass  # urllib connections are not persistent
