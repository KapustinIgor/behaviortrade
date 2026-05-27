from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel

from app.gnn.inference import GNNInference
from app.strategies import STRATEGY_REGISTRY
from app.strategies.signal_engine import REGIME_SCORES, compute_performance

router = APIRouter()


def _get_gnn() -> GNNInference:
    from app.main import _gnn_inference
    return _gnn_inference or GNNInference()

_active_strategies: set[str] = set()
_gnn_disabled: set[str] = set()


@router.get("")
async def list_strategies():
    gnn_out = await _get_gnn().predict()
    regime  = getattr(gnn_out, "regime", "sideways")
    regime_scores = REGIME_SCORES.get(regime, REGIME_SCORES["sideways"])

    # Try to pull cached performance for BTC pnl_30d
    from app.core.redis_client import get_json
    perf_cache = await get_json("price_history_perf:BTC") or {}

    result = []
    for name, cls in STRATEGY_REGISTRY.items():
        strategy = cls(gnn_enabled=(name not in _gnn_disabled))
        signal   = strategy.compute_signal({}, gnn_out)
        cached_strat = (perf_cache.get("strategies") or {}).get(name, {})
        result.append({
            "name":          name,
            "display_name":  cls.display_name,
            "description":   cls.description,
            "signal_state":  signal.state,
            "action":        signal.action,
            "modifier":      signal.modifier,
            "gnn_influence": round(signal.gnn_influence * 100, 1),
            "gnn_enabled":   name not in _gnn_disabled,
            "is_active":     name in _active_strategies,
            "pnl_30d":       cached_strat.get("total_return", 0.0),
            "regime_score":  round(regime_scores.get(name, 0.5) * 100, 1),
        })
    return result


@router.post("/{name}/activate")
async def activate_strategy(name: str = Path(...)):
    if name not in STRATEGY_REGISTRY:
        raise HTTPException(404, f"Strategy '{name}' not found")
    _active_strategies.add(name)
    return {"name": name, "status": "activated"}


@router.post("/{name}/deactivate")
async def deactivate_strategy(name: str = Path(...)):
    _active_strategies.discard(name)
    return {"name": name, "status": "deactivated"}


@router.post("/{name}/toggle-gnn")
async def toggle_gnn(name: str = Path(...)):
    if name in _gnn_disabled:
        _gnn_disabled.discard(name)
        return {"name": name, "gnn_enabled": True}
    _gnn_disabled.add(name)
    return {"name": name, "gnn_enabled": False}


@router.get("/{name}/signal")
async def get_strategy_signal(name: str = Path(...)):
    if name not in STRATEGY_REGISTRY:
        raise HTTPException(404, f"Strategy '{name}' not found")
    gnn_out = await _get_gnn().predict()
    cls = STRATEGY_REGISTRY[name]
    strategy = cls(gnn_enabled=(name not in _gnn_disabled))
    signal = strategy.compute_signal({}, gnn_out)
    return {"name": name, **signal.__dict__, "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/regime-scores")
async def get_regime_scores():
    """Per-strategy GNN regime compatibility scores for the current regime."""
    gnn_out = await _get_gnn().predict()
    regime  = getattr(gnn_out, "regime", "sideways")
    scores  = REGIME_SCORES.get(regime, REGIME_SCORES["sideways"])
    ranked  = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return {
        "regime": regime,
        "gnn_confidence": round(getattr(gnn_out, "confidence", 0.5), 3),
        "scores": {k: round(v, 3) for k, v in scores.items()},
        "recommended": [k for k, _ in ranked[:3]],
        "avoid":       [k for k, _ in ranked[-3:]],
    }


@router.get("/performance/{asset}")
async def get_strategy_performance(
    asset: str = Path(..., description="BTC|ETH|SOL|BNB|XRP"),
):
    """
    Full strategy performance: price history + equity curves + buy/sell signals
    for all 12 strategies and their GNN-weighted combo.
    Cached at the signal_engine layer for 1h.
    """
    gnn_out = await _get_gnn().predict()
    result  = await compute_performance(asset.upper(), gnn_out)

    # Merge real-time pnl_30d into strategy list
    if "strategies" in result:
        for name in result["strategies"]:
            result["strategies"][name]["display_name"] = \
                STRATEGY_REGISTRY[name].display_name if name in STRATEGY_REGISTRY else name

    return result


class BacktestRequest(BaseModel):
    strategies: list[str]
    assets: list[str]
    from_date: str
    to_date: str


@router.post("/backtest")
async def run_backtest(body: BacktestRequest):
    return {"status": "queued", "message": "Backtesting engine coming in Phase 3", "request": body.model_dump()}
