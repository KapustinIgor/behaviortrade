from __future__ import annotations

"""
Strategy Signal Engine — computes technical indicators and generates
buy/sell signals + equity curves from historical price data.

All functions are synchronous pure math; I/O lives in the route layer.
"""

import asyncio
import json
import logging
import math
import time
from typing import Any

logger = logging.getLogger(__name__)

ASSETS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
}

# Kraken pair names (Binance 451-blocked in some regions)
KRAKEN_PAIRS = {
    "bitcoin":     "XBTUSD",
    "ethereum":    "ETHUSD",
    "solana":      "SOLUSD",
    "binancecoin": "BNBUSD",
    "ripple":      "XXRPZUSD",
}

# GNN regime → per-strategy compatibility score (0–1)
REGIME_SCORES: dict[str, dict[str, float]] = {
    "bull": {
        "TREND_FOLLOWING": 0.95, "SWING": 0.85, "FUTURES": 0.80,
        "DAY_TRADING": 0.70, "ALGO_BOT": 0.75, "DCA": 0.60,
        "HODL": 0.90, "NEWS_SENTIMENT": 0.65, "SCALPING": 0.45,
        "RANGE": 0.30, "ARBITRAGE": 0.50, "DEFI_YIELD": 0.70,
    },
    "bear": {
        "TREND_FOLLOWING": 0.40, "SWING": 0.55, "FUTURES": 0.60,
        "DAY_TRADING": 0.65, "ALGO_BOT": 0.70, "DCA": 0.90,
        "HODL": 0.50, "NEWS_SENTIMENT": 0.75, "SCALPING": 0.55,
        "RANGE": 0.35, "ARBITRAGE": 0.60, "DEFI_YIELD": 0.40,
    },
    "sideways": {
        "TREND_FOLLOWING": 0.25, "SWING": 0.60, "FUTURES": 0.35,
        "DAY_TRADING": 0.75, "ALGO_BOT": 0.65, "DCA": 0.80,
        "HODL": 0.70, "NEWS_SENTIMENT": 0.55, "SCALPING": 0.90,
        "RANGE": 0.95, "ARBITRAGE": 0.85, "DEFI_YIELD": 0.75,
    },
    "transition": {
        "TREND_FOLLOWING": 0.50, "SWING": 0.65, "FUTURES": 0.45,
        "DAY_TRADING": 0.70, "ALGO_BOT": 0.80, "DCA": 0.75,
        "HODL": 0.65, "NEWS_SENTIMENT": 0.70, "SCALPING": 0.60,
        "RANGE": 0.55, "ARBITRAGE": 0.65, "DEFI_YIELD": 0.60,
    },
}


# ── Pure indicator math ────────────────────────────────────────────────────────

def ema(prices: list[float], period: int) -> list[float]:
    if not prices:
        return []
    out = [prices[0]]
    k = 2.0 / (period + 1)
    for p in prices[1:]:
        out.append(p * k + out[-1] * (1 - k))
    return out


def rsi(prices: list[float], period: int = 14) -> list[float]:
    """Returns RSI series aligned with prices (first `period` values are None → 50)."""
    if len(prices) < 2:
        return [50.0] * len(prices)
    out = [50.0] * period
    gains, losses = [], []
    for i in range(1, len(prices)):
        d = prices[i] - prices[i - 1]
        gains.append(max(0.0, d))
        losses.append(max(0.0, -d))
        if i >= period:
            ag = sum(gains[-period:]) / period
            al = sum(losses[-period:]) / period
            rs = ag / al if al else 1e9
            out.append(100 - 100 / (1 + rs))
    return out


def macd(prices: list[float], fast: int = 12, slow: int = 26, signal_p: int = 9):
    """Returns (macd_line, signal_line, histogram) all same length as prices."""
    e12 = ema(prices, fast)
    e26 = ema(prices, slow)
    macd_line = [a - b for a, b in zip(e12, e26)]
    sig_line = ema(macd_line, signal_p)
    hist = [m - s for m, s in zip(macd_line, sig_line)]
    return macd_line, sig_line, hist


def bollinger(prices: list[float], period: int = 20, num_std: float = 2.0):
    """Returns (upper, mid, lower) series aligned with prices."""
    upper, mid, lower = [], [], []
    for i in range(len(prices)):
        window = prices[max(0, i - period + 1): i + 1]
        m = sum(window) / len(window)
        std = math.sqrt(sum((p - m) ** 2 for p in window) / len(window))
        mid.append(m)
        upper.append(m + num_std * std)
        lower.append(m - num_std * std)
    return upper, mid, lower


# ── Signal generation per strategy ────────────────────────────────────────────

def _signals_trend_following(prices: list[float]) -> list[str]:
    """MACD crossover + EMA200 filter."""
    ml, sl, hist = macd(prices)
    e200 = ema(prices, 200)
    out = ["hold"] * len(prices)
    for i in range(1, len(prices)):
        cross_up   = hist[i] > 0 and hist[i - 1] <= 0
        cross_down = hist[i] < 0 and hist[i - 1] >= 0
        above200   = prices[i] > e200[i]
        if cross_up and above200:
            out[i] = "buy"
        elif cross_down:
            out[i] = "sell"
    return out


def _signals_swing(prices: list[float]) -> list[str]:
    """RSI(14) mean-reversion."""
    r = rsi(prices, 14)
    out = ["hold"] * len(prices)
    for i in range(1, len(prices)):
        if r[i] < 35 and r[i - 1] >= 35:
            out[i] = "buy"
        elif r[i] > 68 and r[i - 1] <= 68:
            out[i] = "sell"
    return out


def _signals_scalping(prices: list[float]) -> list[str]:
    """Bollinger squeeze — fast in-and-out."""
    up, mid, lo = bollinger(prices, 20)
    out = ["hold"] * len(prices)
    for i in range(1, len(prices)):
        if prices[i] <= lo[i] and prices[i - 1] > lo[i - 1]:
            out[i] = "buy"
        elif prices[i] >= mid[i] and prices[i - 1] < mid[i - 1]:
            out[i] = "sell"
    return out


def _signals_range(prices: list[float]) -> list[str]:
    """Bollinger Band mean reversion (wider bands, slower)."""
    up, mid, lo = bollinger(prices, 20, 2.5)
    out = ["hold"] * len(prices)
    for i in range(1, len(prices)):
        if prices[i] < lo[i]:
            out[i] = "buy"
        elif prices[i] > up[i]:
            out[i] = "sell"
    return out


def _signals_dca(prices: list[float]) -> list[str]:
    """Buy every 24h if price is down vs 48h ago; never explicit sell."""
    out = ["hold"] * len(prices)
    for i in range(48, len(prices), 24):
        if prices[i] < prices[i - 48]:
            out[i] = "buy"
    return out


def _signals_hodl(prices: list[float]) -> list[str]:
    """Buy on day 1, hold forever."""
    out = ["hold"] * len(prices)
    if prices:
        out[0] = "buy"
    return out


def _signals_day_trading(prices: list[float]) -> list[str]:
    """EMA5/EMA20 crossover."""
    e5  = ema(prices, 5)
    e20 = ema(prices, 20)
    out = ["hold"] * len(prices)
    for i in range(1, len(prices)):
        if e5[i] > e20[i] and e5[i - 1] <= e20[i - 1]:
            out[i] = "buy"
        elif e5[i] < e20[i] and e5[i - 1] >= e20[i - 1]:
            out[i] = "sell"
    return out


def _signals_algo_bot(prices: list[float]) -> list[str]:
    """RSI + MACD composite."""
    r = rsi(prices, 14)
    ml, sl, hist = macd(prices)
    out = ["hold"] * len(prices)
    for i in range(1, len(prices)):
        buy_cond  = r[i] < 45 and hist[i] > 0 and hist[i - 1] <= 0
        sell_cond = r[i] > 60 and hist[i] < 0 and hist[i - 1] >= 0
        if buy_cond:
            out[i] = "buy"
        elif sell_cond:
            out[i] = "sell"
    return out


def _signals_news_sentiment(prices: list[float]) -> list[str]:
    """Proxy: buy on 3-candle pullback after uptrend."""
    e50 = ema(prices, 50)
    out = ["hold"] * len(prices)
    for i in range(3, len(prices)):
        uptrend  = prices[i] > e50[i]
        pullback = prices[i] > prices[i - 1] and prices[i - 1] < prices[i - 2] and prices[i - 2] < prices[i - 3]
        if uptrend and pullback:
            out[i] = "buy"
        elif prices[i] < e50[i] and prices[i - 1] >= e50[i - 1]:
            out[i] = "sell"
    return out


def _signals_futures(prices: list[float]) -> list[str]:
    """Same as TREND_FOLLOWING — leverage applied in equity sim."""
    return _signals_trend_following(prices)


def _signals_arbitrage(prices: list[float]) -> list[str]:
    """Mean reversion from 48h MA — simulates spread trading."""
    e48 = ema(prices, 48)
    out = ["hold"] * len(prices)
    for i in range(1, len(prices)):
        dev = (prices[i] - e48[i]) / e48[i] if e48[i] else 0
        if dev < -0.02:
            out[i] = "buy"
        elif dev > 0.02:
            out[i] = "sell"
    return out


def _signals_defi_yield(prices: list[float]) -> list[str]:
    """Accumulation phase detector using 30/90 EMA ratio."""
    e30 = ema(prices, 30)
    e90 = ema(prices, 90)
    out = ["hold"] * len(prices)
    for i in range(1, len(prices)):
        ratio = e30[i] / e90[i] if e90[i] else 1.0
        if ratio > 1.01 and (e30[i - 1] / e90[i - 1] if e90[i - 1] else 1.0) <= 1.01:
            out[i] = "buy"
        elif ratio < 0.99 and (e30[i - 1] / e90[i - 1] if e90[i - 1] else 1.0) >= 0.99:
            out[i] = "sell"
    return out


_SIGNAL_FN = {
    "TREND_FOLLOWING": _signals_trend_following,
    "SWING":           _signals_swing,
    "SCALPING":        _signals_scalping,
    "RANGE":           _signals_range,
    "DCA":             _signals_dca,
    "HODL":            _signals_hodl,
    "DAY_TRADING":     _signals_day_trading,
    "ALGO_BOT":        _signals_algo_bot,
    "NEWS_SENTIMENT":  _signals_news_sentiment,
    "FUTURES":         _signals_futures,
    "ARBITRAGE":       _signals_arbitrage,
    "DEFI_YIELD":      _signals_defi_yield,
}

LEVERAGE = {
    "FUTURES": 3.0,
    "SCALPING": 1.0,
}


# ── Equity simulation ─────────────────────────────────────────────────────────

def simulate_equity(
    prices: list[float],
    signals: list[str],
    leverage: float = 1.0,
    start: float = 10_000.0,
) -> tuple[list[float], dict]:
    """
    Simulate portfolio value over time.
    Returns (equity_pct_series, stats).
    equity_pct_series[i] = % return from start at time i.
    """
    cash      = start
    position  = 0.0   # units of asset held
    entry     = 0.0
    trades    = 0
    wins      = 0
    equity    = []
    events: list[dict] = []

    for i, (price, sig) in enumerate(zip(prices, signals)):
        if sig == "buy" and position == 0.0 and price > 0:
            position  = (cash * leverage) / price
            entry     = price
            cash      = 0.0
        elif sig == "sell" and position > 0.0:
            pnl = position * price - (position * entry)
            cash = position * price
            position = 0.0
            trades += 1
            if pnl > 0:
                wins += 1
            events.append({"idx": i, "action": "sell", "pnl_pct": round(pnl / (position * entry + 1e-9) * 100, 2)})

        current_value = cash + position * price
        equity.append(round((current_value / start - 1) * 100, 3))

    # Close any open position at last price
    if position > 0 and prices:
        cash = position * prices[-1]
        trades += 1
        if prices[-1] > entry:
            wins += 1

    final_value   = cash or start
    total_return  = round((final_value / start - 1) * 100, 2)
    win_rate      = round(wins / trades * 100, 1) if trades else 0.0

    return equity, {
        "total_return": total_return,
        "win_rate":     win_rate,
        "trades":       trades,
    }


# ── Combo signal ──────────────────────────────────────────────────────────────

def combo_signals(all_signals: dict[str, list[str]]) -> list[str]:
    """Majority-vote across selected strategies at each timestep."""
    if not all_signals:
        return []
    length = max(len(v) for v in all_signals.values())
    out = []
    for i in range(length):
        votes = {"buy": 0, "sell": 0, "hold": 0}
        for sigs in all_signals.values():
            votes[sigs[i] if i < len(sigs) else "hold"] += 1
        if votes["buy"] > votes["sell"] and votes["buy"] > votes["hold"]:
            out.append("buy")
        elif votes["sell"] > votes["buy"] and votes["sell"] > votes["hold"]:
            out.append("sell")
        else:
            out.append("hold")
    return out


# ── Data fetching ──────────────────────────────────────────────────────────────

async def fetch_price_history(coin_id: str, hours: int = 200) -> list[dict]:
    """Returns list of {ts, price} dicts, hourly, newest last. Cached 1h in Redis."""
    from app.core.redis_client import get_json, set_json

    cache_key = f"price_history_hourly:{coin_id}:{hours}"
    cached = await get_json(cache_key)
    if cached:
        return cached

    result = await _fetch_kraken(coin_id, hours)
    if not result:
        result = await _fetch_binance(coin_id, hours)

    if result:
        await set_json(cache_key, result, ttl=3600)
    return result


async def _fetch_kraken(coin_id: str, hours: int) -> list[dict]:
    """Fetch hourly OHLCV from Kraken public API."""
    try:
        import httpx
        pair = KRAKEN_PAIRS.get(coin_id)
        if not pair:
            return []
        since = int(time.time()) - (hours + 10) * 3600
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                "https://api.kraken.com/0/public/OHLC",
                params={"pair": pair, "interval": 60, "since": since},
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("error"):
            return []
        result_key = next((k for k in data["result"] if k != "last"), None)
        if not result_key:
            return []
        candles = data["result"][result_key]
        out = [{"ts": int(c[0]), "price": float(c[4])} for c in candles][-hours:]
        logger.info("Fetched %d hourly candles for %s from Kraken", len(out), coin_id)
        return out
    except Exception as e:
        logger.warning("Kraken fetch failed for %s: %s", coin_id, e)
        return []


async def _fetch_binance(coin_id: str, hours: int) -> list[dict]:
    """Fetch hourly OHLCV from Binance public API (fallback)."""
    try:
        import httpx
        from app.gnn.historical_data import PAIRS
        symbol = PAIRS.get(coin_id)
        if not symbol:
            return []
        end_ms   = int(time.time() * 1000)
        start_ms = end_ms - (hours + 10) * 3_600_000
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                "https://api.binance.com/api/v3/klines",
                params={"symbol": symbol, "interval": "1h",
                        "startTime": start_ms, "endTime": end_ms, "limit": hours + 10},
            )
            resp.raise_for_status()
            candles = resp.json()
        out = [{"ts": int(c[0]) // 1000, "price": float(c[4])} for c in candles[-hours:]]
        logger.info("Fetched %d hourly candles for %s from Binance", len(out), coin_id)
        return out
    except Exception as e:
        logger.warning("Binance fetch failed for %s: %s", coin_id, e)
        return []


# ── Main compute function (called by route) ───────────────────────────────────

async def compute_performance(asset: str, gnn_output=None) -> dict:
    """
    Returns full performance data for all 12 strategies on the given asset.
    """
    coin_id = ASSETS.get(asset, "bitcoin")
    history = await fetch_price_history(coin_id, hours=200)

    if len(history) < 30:
        return {"asset": asset, "error": "insufficient price history", "strategies": {}}

    timestamps = [h["ts"] for h in history]
    prices     = [h["price"] for h in history]

    regime = getattr(gnn_output, "regime", "sideways") if gnn_output else "sideways"
    regime_map = REGIME_SCORES.get(regime, REGIME_SCORES["sideways"])

    strategies_out: dict[str, dict] = {}
    all_raw_signals: dict[str, list[str]] = {}

    for name, fn in _SIGNAL_FN.items():
        try:
            raw_sigs = fn(prices)
            all_raw_signals[name] = raw_sigs
            lev = LEVERAGE.get(name, 1.0)
            equity, stats = simulate_equity(prices, raw_sigs, leverage=lev)

            # Sparse signal events for frontend markers
            events = [
                {"ts": timestamps[i], "price": prices[i], "action": raw_sigs[i]}
                for i in range(len(raw_sigs))
                if raw_sigs[i] in ("buy", "sell")
            ][-30:]  # last 30 events max

            strategies_out[name] = {
                "equity":       equity,
                "signals":      events,
                "total_return": stats["total_return"],
                "win_rate":     stats["win_rate"],
                "trades":       stats["trades"],
                "regime_score": round(regime_map.get(name, 0.5), 3),
            }
        except Exception as e:
            logger.debug("Strategy %s failed: %s", name, e)

    # Combo uses all strategies
    combo_sigs = combo_signals(all_raw_signals)
    combo_eq, combo_stats = simulate_equity(prices, combo_sigs)
    combo_events = [
        {"ts": timestamps[i], "price": prices[i], "action": combo_sigs[i]}
        for i in range(len(combo_sigs))
        if combo_sigs[i] in ("buy", "sell")
    ][-30:]

    recommended = sorted(
        regime_map.keys(),
        key=lambda k: regime_map[k],
        reverse=True
    )[:3]

    return {
        "asset":       asset,
        "timestamps":  timestamps,
        "prices":      prices,
        "strategies":  strategies_out,
        "combo": {
            "equity":       combo_eq,
            "signals":      combo_events,
            "total_return": combo_stats["total_return"],
            "win_rate":     combo_stats["win_rate"],
            "trades":       combo_stats["trades"],
        },
        "gnn_regime":  regime,
        "recommended": recommended,
    }
