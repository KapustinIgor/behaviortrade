from __future__ import annotations

from app.gnn.outputs import GNNOutput


def route_signal(gnn_output: GNNOutput, strategy: str) -> dict:
    panic = gnn_output.panic_score
    greed = gnn_output.greed_score
    accum = gnn_output.accumulation_score
    distrib = gnn_output.distribution_score
    confidence = gnn_output.confidence
    regime = gnn_output.regime

    if confidence < 0.6:
        return {"modifier": 1.0, "action": "baseline"}

    if strategy == "DCA":
        if panic > 0.75:
            return {"modifier": 1.75, "action": "accelerate"}
        if greed > 0.80:
            return {"modifier": 0.5, "action": "reduce"}
        if accum > 0.70:
            return {"modifier": 1.3, "action": "increase"}
        return {"modifier": 1.0, "action": "baseline"}

    if strategy == "ARBITRAGE":
        if panic > 0.80:
            return {"modifier": 0.6, "action": "reduce_size"}
        if accum > 0.70:
            return {"modifier": 1.2, "action": "increase_size"}
        return {"modifier": 1.0, "action": "baseline"}

    if strategy == "SCALPING":
        if panic > 0.80:
            return {"modifier": 0.0, "action": "halt"}
        if regime == "sideways":
            return {"modifier": 1.4, "action": "increase"}
        return {"modifier": 1.0, "action": "baseline"}

    if strategy == "FUTURES":
        max_leverage = max(1.0, 10.0 * (1.0 - panic) * confidence)
        return {"modifier": max_leverage / 10.0, "action": "cap_leverage"}

    if strategy == "SWING":
        if regime in ("bull", "bear"):
            return {"modifier": 1.0 + 0.5 * confidence, "action": "boost"}
        return {"modifier": 0.7, "action": "reduce"}

    if strategy == "TREND_FOLLOWING":
        trend_boost = confidence * (greed - panic)
        return {"modifier": 1.0 + trend_boost, "action": "scale"}

    if strategy == "RANGE":
        band_factor = 1.0 + panic * 0.5
        return {"modifier": band_factor, "action": "widen_bands"}

    if strategy == "DEFI_YIELD":
        if distrib > 0.7:
            return {"modifier": 0.5, "action": "reduce_lp"}
        if accum > 0.6:
            return {"modifier": 1.2, "action": "increase_lp"}
        return {"modifier": 1.0, "action": "baseline"}

    if strategy == "HODL":
        if panic > 0.75:
            return {"modifier": 1.0, "action": "alert_panic"}
        return {"modifier": 1.0, "action": "hold"}

    if strategy == "DAY_TRADING":
        size_adj = 1.0 + (greed - panic) * 0.4 * confidence
        return {"modifier": max(0.3, min(2.0, size_adj)), "action": "adjust_size"}

    if strategy in ("NEWS_SENTIMENT", "ALGO_BOT"):
        return {"modifier": 1.0, "action": "inject_gnn_features"}

    return {"modifier": 1.0, "action": "baseline"}
