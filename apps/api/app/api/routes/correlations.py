from __future__ import annotations

"""
Correlation Explorer — computes real Pearson correlations between behavioral
signals and price changes at various lags.

Data sources:
  price series    — Binance hourly candles (via signal_engine cache)
  fear_greed      — Alternative.me (via Redis fear_greed_latest + historical cache)
  social_sentiment— StockTwits scored posts in Redis
  whale_inflow    — blockchain.info whale flows in Redis
  news_sentiment  — scored news items in Redis
"""

import math
import logging
from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)
router = APIRouter()

ASSET_TO_COIN = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
    "BNB": "binancecoin", "XRP": "ripple",
}


# ── Pure math ──────────────────────────────────────────────────────────────────

def _pearson(
    xs: list[float], ys: list[float]
) -> tuple[float, float, float, str, float | None, float | None, str | None]:
    """
    Returns (r, p_value, r_squared, method, spearman_r, spearman_p, spearman_method).

    Tries scipy first for accurate statistics; falls back to normal approximation.
    Both lists must be the same length ≥ 3.
    """
    n = len(xs)
    if n < 3:
        return 0.0, 1.0, 0.0, "approx_normal", None, None, None
    try:
        from scipy import stats as scipy_stats
        import warnings as _warnings
        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore")
            r, p = scipy_stats.pearsonr(xs, ys)
            rho, sp = scipy_stats.spearmanr(xs, ys)
        # scipy returns NaN when one input is constant — treat as zero correlation
        import math as _math
        if _math.isnan(float(r)):
            return 0.0, 1.0, 0.0, "scipy_pearsonr", None, None, None
        method = "scipy_pearsonr"
        spearman_method: str | None = "scipy_spearmanr"
        # spearmanr returns a SpearmanrResult; extract float p
        sp = float(sp) if not _math.isnan(float(sp)) else None
        rho = float(rho) if not _math.isnan(float(rho)) else None
        if sp is None:
            spearman_method = None
    except ImportError:
        mx = sum(xs) / n
        my = sum(ys) / n
        num   = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        dx    = math.sqrt(sum((x - mx) ** 2 for x in xs))
        dy    = math.sqrt(sum((y - my) ** 2 for y in ys))
        if dx == 0 or dy == 0:
            return 0.0, 1.0, 0.0, "approx_normal", None, None, None
        r = num / (dx * dy)
        t = r * math.sqrt(n - 2) / math.sqrt(max(1e-9, 1 - r * r))
        p = 2 * (1 - _norm_cdf(abs(t)))
        rho = None
        sp = None
        method = "approx_normal"
        spearman_method = None
    r = max(-1.0, min(1.0, float(r)))
    p = float(p)
    return round(r, 4), round(p, 4), round(r * r, 4), method, rho, sp, spearman_method


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _pct_changes(prices: list[float]) -> list[float]:
    return [(prices[i] - prices[i - 1]) / prices[i - 1] * 100
            for i in range(1, len(prices))]


def _signal_variance_ok(signal: list[float]) -> bool:
    """Return False if the signal has insufficient variation for reliable correlation."""
    n = len(signal)
    if n < 3:
        return False
    mean = sum(signal) / n
    std = math.sqrt(sum((v - mean) ** 2 for v in signal) / n)
    if std < 1e-6:
        return False
    # More than 90% identical values
    most_common = max(signal, key=signal.count)
    if signal.count(most_common) / n > 0.90:
        return False
    return True


def _lagged_pearson(
    price_changes: list[float], signal: list[float], lag: int
) -> tuple[float, float, float, str, float | None, float | None, str | None]:
    """Compute Pearson R between price_changes and signal shifted by lag hours."""
    if lag >= 0:
        # signal leads price: signal[:-lag] vs price_changes[lag:]
        if lag == 0:
            s, p = signal, price_changes
        else:
            s = signal[:-lag] if lag < len(signal) else []
            p = price_changes[lag:] if lag < len(price_changes) else []
    else:
        # price leads signal: signal[-lag:] vs price_changes[:lag]
        lag_abs = -lag
        s = signal[lag_abs:]
        p = price_changes[:len(signal) - lag_abs]
    n = min(len(s), len(p))
    if n < 5:
        return 0.0, 1.0, 0.0, "approx_normal", None, None, None
    return _pearson(s[:n], p[:n])


# ── Data assembly ──────────────────────────────────────────────────────────────

async def _get_price_changes(coin_id: str) -> list[float]:
    from app.strategies.signal_engine import fetch_price_history
    history = await fetch_price_history(coin_id, hours=200)
    if not history:
        return []
    return _pct_changes([h["price"] for h in history])


async def _get_fear_greed_series(n: int) -> list[float]:
    """Returns up to n hourly fear/greed values (interpolated from daily)."""
    from app.core.redis_client import get_json
    from app.gnn.historical_data import CACHE_DIR
    import json, pathlib

    # Try historical cache first
    cache = CACHE_DIR / "historical_365d.json"
    if cache.exists():
        try:
            raw = json.loads(cache.read_text())
            fg = {int(k): int(v) for k, v in raw.get("fg", {}).items()}
            if fg:
                sorted_vals = [fg[k] for k in sorted(fg)[-n:]]
                return [v / 100.0 for v in sorted_vals]
        except Exception:
            pass

    # Fallback: single current value repeated
    fg_data = await get_json("fear_greed_latest") or {}
    val = fg_data.get("value", 50) / 100.0
    return [val] * n


async def _get_social_sentiment_series(n: int) -> list[float]:
    from app.core.redis_client import get_redis
    import json as _json
    try:
        r = await get_redis()
        raw = await r.lrange("reddit_posts_latest", 0, n - 1)
        scores = []
        for item in raw:
            try:
                p = _json.loads(item)
                scores.append(float(p.get("sentiment_score", 0.0)))
            except Exception:
                pass
        if len(scores) < 5:
            return [0.0] * n
        # Pad/trim to n
        while len(scores) < n:
            scores.append(scores[-1])
        return scores[:n]
    except Exception:
        return [0.0] * n


async def _get_news_sentiment_series(n: int) -> list[float]:
    from app.core.redis_client import get_json
    news = await get_json("news_latest") or []
    scores = [float(item.get("sentiment_score", 0.0)) for item in news]
    if not scores:
        return [0.0] * n
    while len(scores) < n:
        scores.append(scores[-1] if scores else 0.0)
    return scores[:n]


async def _get_whale_series(n: int) -> list[float]:
    from app.core.redis_client import get_json
    flows = await get_json("whale_flows:10") or []
    vals = [min(1.0, float(f.get("btc", 0)) / 500.0) for f in flows]
    if not vals:
        return [0.0] * n
    while len(vals) < n:
        vals.append(vals[-1] if vals else 0.0)
    return vals[:n]


async def _get_reddit_sentiment_series(n: int) -> list[float]:
    """Reddit-specific sentiment from the reddit_posts_latest Redis list."""
    from app.core.redis_client import get_redis
    import json as _json
    try:
        r = await get_redis()
        raw = await r.lrange("reddit_posts_latest", 0, n - 1)
        scores = []
        for item in raw:
            try:
                p = _json.loads(item)
                scores.append(float(p.get("sentiment_score", 0.0)))
            except Exception:
                pass
        if len(scores) < 5:
            return [0.0] * n
        while len(scores) < n:
            scores.append(scores[-1])
        return scores[:n]
    except Exception:
        return [0.0] * n


async def _get_twitter_volume_series(n: int) -> list[float]:
    """
    Twitter/X volume proxy: use social sentiment scores as a volume signal.
    Positive = above-average volume, negative = below average.
    """
    return await _get_social_sentiment_series(n)


async def _get_google_trends_series(n: int) -> list[float]:
    """
    Google Trends proxy: derived from fear/greed + recent price momentum.
    A proper integration would use pytrends but that requires separate scheduling.
    """
    fg = await _get_fear_greed_series(n)
    # Trends correlate with extreme fear/greed (attention spikes)
    return [abs(v - 0.5) * 2 for v in fg]  # 0=neutral attention, 1=max attention


_SIGNAL_SOURCES = {
    "fear_greed":        ("alternative.me",       _get_fear_greed_series),
    "reddit_sentiment":  ("Reddit / StockTwits",   _get_reddit_sentiment_series),
    "social_sentiment":  ("StockTwits/Reddit",     _get_social_sentiment_series),
    "twitter_volume":    ("Twitter/X (proxy)",     _get_twitter_volume_series),
    "news_sentiment":    ("CryptoPanic News",      _get_news_sentiment_series),
    "whale_inflow":      ("blockchain.info",       _get_whale_series),
    "google_trends":     ("Google Trends (proxy)", _get_google_trends_series),
}

LAG_GRID = [-24, -12, -8, -4, 0, 4, 8, 12, 24]

# Sources whose data is real/direct vs proxy/derived
_PROXY_SOURCES  = {"twitter_volume", "google_trends"}
_DIRECT_SOURCES = {"fear_greed", "whale_inflow"}


def _lag_interpretation(lag: int) -> str:
    if lag == 0:
        return "simultaneous — signal and price move together"
    if lag > 0:
        return f"signal leads price by {lag}h — may predict price {lag}h ahead"
    return f"price leads signal by {abs(lag)}h — signal is a lagging indicator"


def _enrich(row: dict) -> dict:
    """Attach human-readable interpretation fields to a correlation row."""
    r   = row["pearson_r"]
    p   = row["p_value"]
    n   = row.get("sample_size", 0)
    lag = row["lag_hours"]
    sig = row["signal_type"]

    abs_r = abs(r)
    if abs_r >= 0.7:
        strength = "strong"
    elif abs_r >= 0.4:
        strength = "moderate"
    elif abs_r >= 0.2:
        strength = "weak"
    else:
        strength = "negligible"

    # Data quality classification
    if sig in _PROXY_SOURCES:
        data_quality = "proxy"
        source_type  = "derived"
        warning: str | None = (
            f"'{sig}' is a proxy derived from other signals, "
            "not a direct measurement. Treat with caution."
        )
    elif sig in _DIRECT_SOURCES:
        data_quality = "real"
        source_type  = "direct"
        warning = None
    else:
        data_quality = "mixed"
        source_type  = "composite"
        warning = None

    # Variance check: if signal has insufficient variation, override quality
    _signal = row.pop("_signal", None)
    variance_ok = _signal_variance_ok(_signal) if _signal is not None else True
    if not variance_ok:
        data_quality = "insufficient"
        warning = "Signal has insufficient variation for reliable correlation."

    # Updated actionability: ALL conditions must hold
    is_actionable = (
        abs_r >= 0.4
        and p < 0.05
        and n >= 30
        and data_quality == "real"
        and variance_ok
        and lag > 0
    )

    # Actionability reason
    if not variance_ok:
        actionability_reason = "No actionable signal: signal has insufficient variation."
    elif abs_r < 0.2:
        actionability_reason = "No actionable signal: correlation is negligible."
    elif p >= 0.05:
        actionability_reason = "No actionable signal: p-value not significant."
    elif n < 30:
        actionability_reason = "No actionable signal: insufficient sample size."
    elif data_quality in ("proxy", "mixed"):
        actionability_reason = "Supporting signal only: source is proxy/derived."
    elif lag <= 0:
        actionability_reason = "No actionable signal: lag is not predictive (lag <= 0)."
    elif abs_r < 0.4:
        actionability_reason = "No actionable signal: correlation is negligible."
    else:
        actionability_reason = (
            "Potential signal: real data, leading lag, moderate correlation, significant."
        )

    # Pull through extra stats fields from _pearson if available
    p_value_method   = row.pop("p_value_method", "approx_normal")
    spearman_r       = row.pop("spearman_r", None)
    spearman_p_value = row.pop("spearman_p_value", None)
    spearman_method  = row.pop("spearman_method", None)

    row.update({
        "strength":               strength,
        "direction":              "positive" if r >= 0 else "negative",
        "is_actionable":          is_actionable,
        "effective_sample_size":  n,
        "data_quality":           data_quality,
        "source_type":            source_type,
        "warning":                warning,
        "lag_interpretation":     _lag_interpretation(lag),
        "actionability_reason":   actionability_reason,
        "p_value_method":         p_value_method,
        "spearman_r":             round(spearman_r, 4) if spearman_r is not None else None,
        "spearman_p_value":       round(spearman_p_value, 4) if spearman_p_value is not None else None,
        "spearman_method":        spearman_method,
        "signal_points_available": n,
        "price_points_available":  n,
    })
    return row


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("")
async def get_correlations(
    signal_type: str = Query(default=None),
    asset: str = Query(default="BTC"),
    lag_hours: float = Query(default=None),
    limit: int = Query(default=20, le=100),
):
    coin_id = ASSET_TO_COIN.get(asset.upper(), "bitcoin")
    price_changes = await _get_price_changes(coin_id)
    if not price_changes:
        return {
            "asset": asset,
            "correlations": [],
            "status": "unavailable",
            "warning": "Price history unavailable — cannot compute correlations.",
        }

    results = []
    tested_signals_set = set()
    tested_lags_set: set[int] = set()

    for sig_type, (source, getter) in _SIGNAL_SOURCES.items():
        if signal_type and sig_type != signal_type:
            continue
        sig_data = await getter(len(price_changes))
        lags = [int(lag_hours)] if lag_hours is not None else LAG_GRID
        for lag in lags:
            r, p, r2, method, rho, sp, sp_method = _lagged_pearson(price_changes, sig_data, lag)
            tested_signals_set.add(sig_type)
            tested_lags_set.add(lag)
            row = {
                "signal_type":     sig_type,
                "signal_source":   source,
                "asset":           asset,
                "lag_hours":       lag,
                "pearson_r":       r,
                "p_value":         p,
                "r_squared":       r2,
                "sample_size":     len(price_changes),
                "p_value_method":  method,
                "spearman_r":      rho,
                "spearman_p_value": sp,
                "spearman_method": sp_method,
            }
            results.append(_enrich(row))

    tested_signals = len(tested_signals_set)
    tested_lags    = len(tested_lags_set)
    multiple_testing_warning: str | None = None
    if tested_signals * tested_lags > 1:
        multiple_testing_warning = (
            "Multiple comparisons were tested. Some correlations may be spurious. "
            "Apply Bonferroni or FDR correction before acting on these results."
        )

    results.sort(key=lambda x: abs(x["pearson_r"]), reverse=True)
    return {
        "asset":                    asset,
        "correlations":             results[:limit],
        "tested_lags":              tested_lags,
        "tested_signals":           tested_signals,
        "multiple_testing_warning": multiple_testing_warning,
    }


@router.post("/compute")
async def compute_correlations(asset: str = Query(default="BTC")):
    return {"status": "ok", "asset": asset, "message": "Use GET /correlations for real-time results"}


@router.get("/top")
async def get_top_correlations(
    asset: str = Query(default="BTC"),
    limit: int = Query(default=10, le=50),
):
    coin_id = ASSET_TO_COIN.get(asset.upper(), "bitcoin")
    price_changes = await _get_price_changes(coin_id)
    if not price_changes:
        # No fake fallback — return an honest empty response
        return {
            "asset": asset,
            "top_correlations": [],
            "status": "unavailable",
            "warning": (
                "Price history could not be fetched. "
                "Correlations require live data and cannot be estimated."
            ),
        }

    # Find best lag per signal type
    best: list[dict] = []
    for sig_type, (source, getter) in _SIGNAL_SOURCES.items():
        sig_data = await getter(len(price_changes))
        best_r, best_lag = 0.0, 0
        best_p, best_r2  = 1.0, 0.0
        best_method      = "approx_normal"
        best_rho: float | None = None
        best_sp:  float | None = None
        best_sp_method: str | None = None
        for lag in LAG_GRID:
            r, p, r2, method, rho, sp, sp_method = _lagged_pearson(price_changes, sig_data, lag)
            if abs(r) > abs(best_r):
                best_r, best_lag, best_p, best_r2 = r, lag, p, r2
                best_method = method
                best_rho    = rho
                best_sp     = sp
                best_sp_method = sp_method
        row = {
            "signal_type":     sig_type,
            "signal_source":   source,
            "lag_hours":       best_lag,
            "pearson_r":       best_r,
            "p_value":         best_p,
            "r_squared":       best_r2,
            "sample_size":     len(price_changes),
            "p_value_method":  best_method,
            "spearman_r":      best_rho,
            "spearman_p_value": best_sp,
            "spearman_method": best_sp_method,
        }
        best.append(_enrich(row))

    tested_signals = len(_SIGNAL_SOURCES)
    tested_lags    = len(LAG_GRID)
    multiple_testing_warning: str | None = None
    if tested_signals * tested_lags > 1:
        multiple_testing_warning = (
            "Multiple comparisons were tested. Some correlations may be spurious. "
            "Apply Bonferroni or FDR correction before acting on these results."
        )

    best.sort(key=lambda x: abs(x["pearson_r"]), reverse=True)
    return {
        "asset":                    asset,
        "top_correlations":         best[:limit],
        "tested_lags":              tested_lags,
        "tested_signals":           tested_signals,
        "multiple_testing_warning": multiple_testing_warning,
    }
