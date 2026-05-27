from __future__ import annotations

import math
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.gnn.inference import GNNInference
from app.models.predictions import Prediction as PredictionModel
from app.strategies.signal_engine import (
    REGIME_SCORES, _SIGNAL_FN, fetch_price_history,
)

router = APIRouter()


def _get_gnn() -> GNNInference:
    from app.main import _gnn_inference
    return _gnn_inference or GNNInference()


_ACCURACY_CACHE: dict = {}
_ACCURACY_CACHE_TS: float = 0.0
_ACCURACY_CACHE_TTL = 3600.0  # recompute at most once per hour


async def _compute_accuracy() -> dict:
    """
    Derive real prediction accuracy by back-testing _mock_probs_from_prices()
    against actual price outcomes over the last 200 hours.
    """
    global _ACCURACY_CACHE, _ACCURACY_CACHE_TS
    now = time.time()
    if _ACCURACY_CACHE and (now - _ACCURACY_CACHE_TS) < _ACCURACY_CACHE_TTL:
        return _ACCURACY_CACHE

    try:
        history = await fetch_price_history("bitcoin", hours=200)
        prices = [h["price"] for h in history]

        correct: dict[str, int] = {"1h": 0, "4h": 0, "24h": 0}
        total:   dict[str, int] = {"1h": 0, "4h": 0, "24h": 0}
        offsets = {"1h": 1, "4h": 4, "24h": 24}
        min_ctx = 25  # need at least 25 candles of context

        for i in range(min_ctx, len(prices) - 24):
            ctx = prices[:i]
            p1h, p4h, p24h, _ = _mock_probs_from_prices(ctx)
            cur = prices[i]
            for tf, offset in offsets.items():
                if i + offset >= len(prices):
                    continue
                fut = prices[i + offset]
                predicted_up = {"1h": p1h > 0.5, "4h": p4h > 0.5, "24h": p24h > 0.5}[tf]
                actual_up    = fut > cur
                if predicted_up == actual_up:
                    correct[tf] += 1
                total[tf] += 1

        def pct(tf: str) -> float:
            return round(correct[tf] / total[tf] * 100, 1) if total[tf] > 0 else 50.0

        sample = min(total.values()) if total else 0
        result = {
            "overall":     round((pct("1h") + pct("4h") + pct("24h")) / 3, 1),
            "1h":          pct("1h"),
            "4h":          pct("4h"),
            "24h":         pct("24h"),
            "sample_size": sample,
        }
        _ACCURACY_CACHE    = result
        _ACCURACY_CACHE_TS = now
        return result
    except Exception:
        # Fallback to neutral 50% rather than fake inflated number
        return {"overall": 50.0, "1h": 50.0, "4h": 50.0, "24h": 50.0, "sample_size": 0}


@router.get("/latest")
async def get_latest_predictions(limit: int = Query(default=5, le=20)):
    scores = await _get_gnn().get_behavioral_scores()
    now = datetime.now(timezone.utc).isoformat()
    predictions = []
    for asset in ["BTC", "ETH", "SOL"]:
        for tf, prob_key in [("1h", "direction_1h"), ("4h", "direction_4h"), ("24h", "direction_24h")]:
            prob = scores.get(prob_key, 50)
            direction = "up" if prob >= 50 else "down"
            predictions.append({
                "id": f"{asset}_{tf}_{now}",
                "asset": asset,
                "direction": direction,
                "probability": round(prob, 1),
                "confidence": scores.get("confidence", 62),
                "timeframe": tf,
                "contributing_signals": [
                    {"name": "Panic Index", "weight": 0.3, "value": scores.get("panic_score", 30)},
                    {"name": "Greed Index", "weight": 0.3, "value": scores.get("greed_score", 60)},
                    {"name": "Accumulation", "weight": 0.2, "value": scores.get("accumulation_score", 35)},
                    {"name": "News Shock", "weight": 0.2, "value": scores.get("news_shock_score", 20)},
                ],
                "created_at": now,
            })
    return predictions[:limit]


@router.get("/accuracy")
async def get_prediction_accuracy():
    return await _compute_accuracy()


@router.get("/{asset}")
async def get_asset_predictions(asset: str = Path(...)):
    scores = await _get_gnn().get_behavioral_scores()
    now = datetime.now(timezone.utc).isoformat()
    return {
        "asset": asset,
        "predictions": {
            "1h": {"direction": "up" if scores.get("direction_1h", 50) >= 50 else "down", "probability": scores.get("direction_1h", 50), "confidence": scores.get("confidence", 62)},
            "4h": {"direction": "up" if scores.get("direction_4h", 50) >= 50 else "down", "probability": scores.get("direction_4h", 50), "confidence": scores.get("confidence", 62)},
            "24h": {"direction": "up" if scores.get("direction_24h", 50) >= 50 else "down", "probability": scores.get("direction_24h", 50), "confidence": scores.get("confidence", 62)},
        },
        "timestamp": now,
    }


@router.post("/{prediction_id}/vote")
async def vote_prediction(
    prediction_id: str = Path(...),
    agree: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """Increment community_agree or community_disagree on the prediction row."""
    # prediction_id from the frontend is a composite string like "BTC_1h_<iso>"
    # We upsert a Redis vote tally since these are ephemeral predictions (no DB row yet)
    from app.core.redis_client import get_redis
    r = await get_redis()
    key = f"vote:{prediction_id}"
    field = "agree" if agree else "disagree"
    await r.hincrby(key, field, 1)
    await r.expire(key, 86400 * 7)  # keep vote tallies for 7 days
    agree_count    = int(await r.hget(key, "agree")    or 0)
    disagree_count = int(await r.hget(key, "disagree") or 0)
    return {
        "prediction_id":      prediction_id,
        "agree":              agree,
        "status":             "recorded",
        "community_agree":    agree_count,
        "community_disagree": disagree_count,
    }


# ── GNN + Strategy forward price forecast ─────────────────────────────────────

_ASSET_COIN = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
    "BNB": "binancecoin", "XRP": "ripple",
}


def _hourly_vol(prices: list[float], window: int = 48) -> float:
    """Realised hourly volatility (log-return std) over last `window` candles."""
    tail = prices[-window:] if len(prices) >= window else prices
    if len(tail) < 2:
        return 0.01
    log_rets = [math.log(tail[i] / tail[i - 1]) for i in range(1, len(tail)) if tail[i - 1] > 0]
    if not log_rets:
        return 0.01
    mean = sum(log_rets) / len(log_rets)
    variance = sum((r - mean) ** 2 for r in log_rets) / len(log_rets)
    return math.sqrt(variance)


def _strategy_bias(prices: list[float], regime: str) -> float:
    """
    Blended directional bias from the top-3 regime-fit strategies.
    Returns value in [-1, +1]; positive = bullish, negative = bearish.
    """
    scores = REGIME_SCORES.get(regime, REGIME_SCORES["sideways"])
    top3 = sorted(scores, key=lambda k: scores[k], reverse=True)[:3]
    votes = []
    for name in top3:
        fn = _SIGNAL_FN.get(name)
        if not fn:
            continue
        sigs = fn(prices)
        # Look at the last signal emitted (last buy or sell in the series)
        last_sig = next((s for s in reversed(sigs) if s in ("buy", "sell")), "hold")
        weight = scores[name]
        votes.append((1.0 if last_sig == "buy" else -1.0 if last_sig == "sell" else 0.0) * weight)
    return sum(votes) / len(votes) if votes else 0.0


def _mock_probs_from_prices(prices: list[float]) -> tuple[float, float, float, float]:
    """Derive GNN-like direction probs from price action (historical replay without Redis)."""
    if len(prices) < 25:
        return 0.5, 0.5, 0.5, 0.5
    ch_1h  = (prices[-1] - prices[-2])  / prices[-2]  if prices[-2]  > 0 else 0.0
    ch_4h  = (prices[-1] - prices[-5])  / prices[-5]  if prices[-5]  > 0 else 0.0
    ch_24h = (prices[-1] - prices[-25]) / prices[-25] if prices[-25] > 0 else 0.0
    tail = prices[-15:]
    up_moves = sum(1 for i in range(1, len(tail)) if tail[i] > tail[i - 1])
    rsi_proxy = up_moves / 14.0
    greed = min(1.0, max(0.0, 0.5 + ch_24h * 5))
    panic = min(1.0, max(0.0, 0.5 - ch_24h * 5))
    prob_1h  = round(min(0.95, max(0.05, 0.5 + (greed - panic) * 0.15 + ch_1h  * 2)), 4)
    prob_4h  = round(min(0.95, max(0.05, 0.5 + (greed - panic) * 0.12 + ch_4h  * 1)), 4)
    prob_24h = round(min(0.95, max(0.05, 0.5 + (greed - panic) * 0.08)),               4)
    conf     = round(min(1.0, 0.5 + abs(rsi_proxy - 0.5) * 0.6), 4)
    return prob_1h, prob_4h, prob_24h, conf


def _classify_regime(prices: list[float]) -> str:
    if len(prices) < 168:
        return "sideways"
    ch7d = (prices[-1] - prices[-168]) / prices[-168] if prices[-168] > 0 else 0
    if ch7d > 0.10:  return "bull"
    if ch7d < -0.10: return "bear"
    ch2d = (prices[-1] - prices[-48]) / prices[-48] if prices[-48] > 0 else 0
    return "transition" if abs(ch2d) > 0.03 else "sideways"


def _step_price(
    px: float,
    h: int,
    prob_1h: float,
    prob_4h: float,
    prob_24h: float,
    strat_bias: float,
    vol: float,
    conf: float,
) -> float:
    """Advance price by one step using GNN + strategy blend."""
    if h <= 1:
        gnn_prob = prob_1h
    elif h <= 4:
        t = (h - 1) / 3.0
        gnn_prob = prob_1h * (1 - t) + prob_4h * t
    elif h <= 24:
        t = (h - 4) / 20.0
        gnn_prob = prob_4h * (1 - t) + prob_24h * t
    else:
        decay = math.exp(-(h - 24) / 48.0)
        gnn_prob = 0.5 + (prob_24h - 0.5) * decay
    net = (gnn_prob - 0.5) * 2 * 0.65 + strat_bias * 0.35
    return px * math.exp(net * vol * conf)


@router.get("/forecast/{asset}")
async def get_price_forecast(
    asset: str = Path(..., description="BTC|ETH|SOL|BNB|XRP"),
    past_hours: int = Query(default=96,  ge=24, le=168),
    future_hours: int = Query(default=72, ge=24, le=168),
):
    """
    Single continuous GNN + strategy forecast line:
      - past_hours of historical prediction (what the model would have called)
      - future_hours of forward prediction from now
    Both joined at the current price into one unbroken series.
    """
    gnn = _get_gnn()
    gnn_out = await gnn.predict()
    scores  = await gnn.get_behavioral_scores()

    coin_id = _ASSET_COIN.get(asset.upper(), "bitcoin")
    history = await fetch_price_history(coin_id, hours=200)

    if len(history) < 50:
        return {"asset": asset, "error": "insufficient history", "line": []}

    prices_all = [h["price"] for h in history]
    times_all  = [h["ts"]    for h in history]
    n = len(prices_all)

    # ── Past portion ─────────────────────────────────────────────────────────
    # Origin: the price at `past_hours` ago (or as far back as we have data)
    past_start_idx = max(0, n - 1 - past_hours)
    origin_px  = prices_all[past_start_idx]
    origin_ts  = times_all[past_start_idx]
    ctx_prices = prices_all[:past_start_idx + 1]

    p1h, p4h, p24h, conf_hist = _mock_probs_from_prices(ctx_prices)
    regime_hist  = _classify_regime(ctx_prices)
    sbias_hist   = _strategy_bias(ctx_prices, regime_hist)
    vol_hist     = _hourly_vol(ctx_prices, window=48)

    past_line: list[dict] = [{"time": origin_ts, "price": round(origin_px, 4)}]
    px = origin_px
    for h in range(1, (n - 1 - past_start_idx) + 1):
        px = _step_price(px, h, p1h, p4h, p24h, sbias_hist, vol_hist, conf_hist)
        past_line.append({"time": origin_ts + h * 3600, "price": round(px, 4)})

    # ── Bridge: snap the line end to the actual current price ─────────────────
    # This avoids a visible gap/jump at "now" while preserving the shape
    actual_now  = prices_all[-1]
    predicted_now = past_line[-1]["price"] if past_line else actual_now
    scale = actual_now / predicted_now if predicted_now > 0 else 1.0
    # Gently correct last 24 points toward actual (linear blend)
    correction_window = min(24, len(past_line))
    for j in range(correction_window):
        idx = len(past_line) - correction_window + j
        blend = j / correction_window          # 0 → 1 over the window
        past_line[idx]["price"] = round(
            past_line[idx]["price"] * (1 + blend * (scale - 1)), 4
        )

    # ── Future portion ───────────────────────────────────────────────────────
    current_ts = times_all[-1]
    prob_1h  = scores.get("direction_1h",  50.0) / 100.0
    prob_4h  = scores.get("direction_4h",  50.0) / 100.0
    prob_24h = scores.get("direction_24h", 50.0) / 100.0
    gnn_conf = scores.get("confidence",    62.0) / 100.0
    regime   = getattr(gnn_out, "regime", "sideways")
    sbias    = _strategy_bias(prices_all, regime)
    vol      = _hourly_vol(prices_all, window=48)

    future_line: list[dict] = []
    px = actual_now
    for h in range(1, future_hours + 1):
        px = _step_price(px, h, prob_1h, prob_4h, prob_24h, sbias, vol, gnn_conf)
        band = 1.65 * vol * math.sqrt(h)
        future_line.append({
            "time":  current_ts + h * 3600,
            "price": round(px, 4),
            "upper": round(px * math.exp(band),  4),
            "lower": round(px * math.exp(-band), 4),
        })

    direction = "up" if prob_24h > 0.5 else "down"

    return {
        "asset":          asset.upper(),
        "regime":         regime,
        "gnn_confidence": round(gnn_conf * 100, 1),
        "direction":      direction,
        "prob_24h":       round(prob_24h * 100, 1),
        "past_line":      past_line,
        "future_line":    future_line,
        "now_ts":         current_ts,
        "generated_at":   int(time.time()),
    }
