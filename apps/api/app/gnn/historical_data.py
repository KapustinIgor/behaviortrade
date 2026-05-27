from __future__ import annotations

"""
Fetches and caches 1-year hourly price data from CoinGecko (free, no auth)
and daily Fear & Greed from Alternative.me.

CoinGecko /market_chart/range returns hourly data for windows up to 90 days.
We paginate through 89-day windows to cover the full requested period.

Cache is stored at apps/api/data/historical/historical_{days}d.json
"""

import asyncio
import json
import logging
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

CACHE_DIR   = Path(__file__).parent.parent.parent / "data" / "historical"
COINGECKO   = "https://api.coingecko.com/api/v3"
FNG_BASE    = "https://api.alternative.me"

# CoinGecko coin IDs
PAIRS: dict[str, str] = {
    "bitcoin":     "bitcoin",
    "ethereum":    "ethereum",
    "solana":      "solana",
    "binancecoin": "binancecoin",
    "ripple":      "ripple",
}

# Kraken pairs kept for the live signal_engine (short-window fetches)
KRAKEN_PAIRS: dict[str, str] = {
    "bitcoin":     "XBTUSD",
    "ethereum":    "ETHUSD",
    "solana":      "SOLUSD",
    "binancecoin": "BNBUSD",
    "ripple":      "XXRPZUSD",
}

_WINDOW_DAYS = 89   # CoinGecko returns hourly data for windows ≤ 90 days


async def _fetch_coingecko_window(
    client: httpx.AsyncClient,
    coin_id: str,
    from_ts: int,
    to_ts: int,
    *,
    max_retries: int = 5,
) -> list[list]:
    """Fetch one 89-day hourly window from CoinGecko. Returns [[ts_ms, price], ...]."""
    delay = 30.0
    for attempt in range(max_retries):
        resp = await client.get(
            f"{COINGECKO}/coins/{coin_id}/market_chart/range",
            params={"vs_currency": "usd", "from": from_ts, "to": to_ts},
            headers={"User-Agent": "BehaviorTrade/1.0"},
        )
        if resp.status_code == 429:
            wait = delay * (2 ** attempt)
            logger.warning("  CoinGecko 429 for %s — waiting %.0fs (attempt %d/%d)",
                           coin_id, wait, attempt + 1, max_retries)
            await asyncio.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json().get("prices", [])
    raise RuntimeError(f"CoinGecko rate-limited after {max_retries} retries for {coin_id}")


async def _fetch_coingecko_hourly(
    client: httpx.AsyncClient,
    coin_id: str,
    days: int,
) -> list[list]:
    """
    Fetch full hourly history by paginating through 89-day windows.
    Returns [[ts_ms, price], ...] oldest first.
    """
    now      = int(time.time())
    start    = now - days * 86400
    window_s = _WINDOW_DAYS * 86400

    all_prices: list[list] = []
    cursor = start

    while cursor < now:
        end = min(cursor + window_s, now)
        try:
            batch = await _fetch_coingecko_window(client, coin_id, cursor, end)
            all_prices.extend(batch)
            logger.debug("  CoinGecko %s: +%d pts (window %s→%s)",
                         coin_id, len(batch),
                         time.strftime("%Y-%m-%d", time.gmtime(cursor)),
                         time.strftime("%Y-%m-%d", time.gmtime(end)))
        except Exception as e:
            logger.warning("  CoinGecko window failed for %s: %s", coin_id, e)
        cursor = end + 1
        await asyncio.sleep(7.0)   # CoinGecko free tier: ~10 req/min → ≥6s safe margin

    # Deduplicate by hour-aligned timestamp
    seen: set[int] = set()
    unique: list[list] = []
    for p in all_prices:
        hour_ts = (int(p[0]) // 1000 // 3600) * 3600
        if hour_ts not in seen:
            seen.add(hour_ts)
            unique.append(p)
    unique.sort(key=lambda p: p[0])
    return unique


async def _fetch_fear_greed(client: httpx.AsyncClient, limit: int) -> list[dict]:
    resp = await client.get(f"{FNG_BASE}/fng/", params={"limit": limit, "format": "json"})
    resp.raise_for_status()
    return resp.json().get("data", [])


def _coingecko_to_hourly(prices: list[list]) -> dict[int, dict]:
    """
    Convert CoinGecko [[ts_ms, price], ...] to hourly dict.
    CoinGecko only returns close price — open/high/low approximate from neighbors.
    """
    out: dict[int, dict] = {}
    for i, (ts_ms, price) in enumerate(prices):
        ts = (int(ts_ms) // 1000 // 3600) * 3600
        out[ts] = {
            "open":   price,
            "high":   price,
            "low":    price,
            "close":  price,
            "volume": 0.0,
        }
    return out


def _candles_to_hourly(candles: list[list]) -> dict[int, dict]:
    """Legacy OHLCV format — kept for signal_engine compatibility."""
    out: dict[int, dict] = {}
    for c in candles:
        ts = (c[0] // 1000 // 3600) * 3600
        out[ts] = {
            "open":   float(c[1]),
            "high":   float(c[2]),
            "low":    float(c[3]),
            "close":  float(c[4]),
            "volume": float(c[5]) if len(c) > 5 else 0.0,
        }
    return out


def _fg_to_hourly(fg_items: list[dict]) -> dict[int, int]:
    """Expand daily fear & greed to every hour of that day."""
    out: dict[int, int] = {}
    for item in fg_items:
        day_ts = int(item["timestamp"])
        day_ts = (day_ts // 86400) * 86400
        val = int(item["value"])
        for h in range(24):
            out[day_ts + h * 3600] = val
    return out


async def load_or_fetch(days: int = 365) -> dict:
    """
    Returns:
        {
          "prices": { "bitcoin": {ts: {open,high,low,close,volume}}, ... },
          "fg":     { ts: int_value_0_100 },
          "days":   int
        }
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"historical_{days}d.json"

    if cache_file.exists():
        logger.info("Loading cached data from %s", cache_file)
        with open(cache_file) as f:
            raw = json.load(f)
        # JSON keys are strings — convert back to int
        prices = {
            coin: {int(k): v for k, v in hourly.items()}
            for coin, hourly in raw["prices"].items()
        }
        fg = {int(k): v for k, v in raw["fg"].items()}
        return {"prices": prices, "fg": fg, "days": days}

    logger.info("Fetching %d days of historical data from CoinGecko + Alternative.me...", days)
    prices: dict[str, dict[int, dict]] = {}

    async with httpx.AsyncClient(timeout=60) as client:
        for i, coin_id in enumerate(PAIRS):
            if i > 0:
                logger.info("  Pausing 15s before next coin...")
                await asyncio.sleep(15.0)
            logger.info("  %s...", coin_id)
            raw = await _fetch_coingecko_hourly(client, coin_id, days)
            prices[coin_id] = _coingecko_to_hourly(raw)
            logger.info("    %d hourly candles", len(prices[coin_id]))

        logger.info("  Fear & Greed...")
        fg_raw = await _fetch_fear_greed(client, min(days, 900))

    fg = _fg_to_hourly(fg_raw)
    logger.info("  Fear & Greed entries: %d", len(fg))

    # Cache with string keys (JSON requirement)
    with open(cache_file, "w") as f:
        json.dump({
            "prices": {coin: {str(k): v for k, v in h.items()} for coin, h in prices.items()},
            "fg":     {str(k): v for k, v in fg.items()},
            "days":   days,
        }, f)
    logger.info("Cached → %s", cache_file)

    return {"prices": prices, "fg": fg, "days": days}


def build_aligned_timestamps(data: dict, step_hours: int = 4) -> list[int]:
    """
    Return sorted list of timestamps where ALL coins have data,
    subsampled every step_hours.
    """
    sets = [set(data["prices"][c].keys()) for c in PAIRS]
    common = set.intersection(*sets)
    sorted_ts = sorted(common)
    step_s = step_hours * 3600
    return [ts for ts in sorted_ts if ts % step_s == 0]


def price_features_at(data: dict, ts: int) -> dict[str, dict]:
    """
    Returns per-coin price info at timestamp ts including derived changes.
    {
      "bitcoin": {"price": float, "change_1h": float, "change_24h": float, "change_7d": float},
      ...
    }
    """
    out: dict[str, dict] = {}
    for coin, hourly in data["prices"].items():
        snap = hourly.get(ts)
        if not snap:
            continue
        price = snap["close"]

        def pct_change(offset_h: int) -> float:
            prev = hourly.get(ts - offset_h * 3600)
            if prev and prev["close"]:
                return (price - prev["close"]) / prev["close"] * 100.0
            return 0.0

        out[coin] = {
            "price":      price,
            "change_1h":  pct_change(1),
            "change_24h": pct_change(24),
            "change_7d":  pct_change(168),
            "volume":     snap["volume"],
        }
    return out


def labels_at(data: dict, ts: int) -> dict | None:
    """
    Compute training labels for timestamp ts.
    Returns None if future data is unavailable.
    """
    btc = data["prices"].get("bitcoin", {})
    now  = btc.get(ts)
    h1   = btc.get(ts + 3_600)
    h4   = btc.get(ts + 4 * 3_600)
    h24  = btc.get(ts + 24 * 3_600)

    if not (now and h1 and h4 and h24):
        return None

    p = now["close"]
    c7d = 0.0
    prev7 = btc.get(ts - 168 * 3600)
    if prev7 and prev7["close"]:
        c7d = (p - prev7["close"]) / prev7["close"] * 100.0

    regime = (
        "bull"       if c7d > 10
        else "bear"  if c7d < -10
        else "sideways"
    )

    return {
        "dir_1h":   1 if h1["close"]  > p else 0,
        "dir_4h":   1 if h4["close"]  > p else 0,
        "dir_24h":  1 if h24["close"] > p else 0,
        "regime":   regime,
    }
