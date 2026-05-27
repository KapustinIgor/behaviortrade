from __future__ import annotations

"""GNN graph visualization endpoint."""

import logging
import math
import time
from typing import Any

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Color maps ────────────────────────────────────────────────────────────────

_NODE_COLORS: dict[str, str] = {
    "exchange":          "#f59e0b",
    "whale_wallet":      "#60a5fa",
    "dex_pool":          "#34d399",
    "news_source":       "#f472b6",
    "social_account":    "#a78bfa",
    "retail_cluster":    "#fb923c",
    "on_chain_contract": "#94a3b8",
}

_EDGE_COLORS: dict[str, str] = {
    "fund_flow":               "#60a5fa",
    "trade_volume":            "#f59e0b",
    "social_influence":        "#a78bfa",
    "news_citation":           "#f472b6",
    "liquidity_provision":     "#34d399",
    "historical_correlation":  "#6b7280",
}

# Human-readable labels per node type (in node-index order)
_NODE_LABELS: dict[str, list[str]] = {
    "exchange": [
        "Binance", "Coinbase", "Kraken", "OKX", "Bybit",
        "Huobi", "KuCoin", "Gemini", "Bitfinex", "Bitstamp",
    ],
    "whale_wallet":      [f"Whale-{i:02d}" for i in range(20)],
    "dex_pool":          ["Uniswap-v3", "Curve", "Aave-v3", "Compound", "dYdX"],
    "news_source":       ["CoinDesk", "CoinTelegraph", "TheBlock", "Decrypt", "Bitcoin.com"],
    "social_account":    [f"Social-{i:02d}" for i in range(5)],
    "retail_cluster":    [f"Retail-{i:02d}" for i in range(5)],
    "on_chain_contract": ["Bridge", "Token-A", "Token-B"],
}

# Node type → group integer (for D3 / vis-network grouping)
_NODE_GROUPS: dict[str, int] = {
    "exchange":          0,
    "whale_wallet":      1,
    "dex_pool":          2,
    "news_source":       3,
    "social_account":    4,
    "retail_cluster":    5,
    "on_chain_contract": 6,
}

# Feature index → named metric key
_FEATURE_METRICS = {
    7: "volume_rank",
    2: "change_24h",
    4: "sentiment",
    8: "fg_signal",
}


def _size_from_volume_rank(vol_rank: float) -> float:
    """Map volume_rank (0–1) to node size in [0.3, 1.0]."""
    return round(0.3 + vol_rank * 0.7, 3)


def _extract_metrics(features: list[float]) -> dict[str, float]:
    """Pull named metrics out of the raw 16-dim feature vector."""
    return {
        "volume_rank": round(features[7], 3),
        "change_24h":  round((features[2] - 0.5) * 200.0, 2),   # back to pct-ish
        "sentiment":   round(features[4], 3),
        "fg_signal":   round(features[8], 3),
    }


@router.get("/graph")
async def get_graph() -> dict[str, Any]:
    """Return the current BehaviorGAT graph as visualization-friendly JSON."""
    try:
        from app.gnn.graph_builder import GraphBuilder
        gb = GraphBuilder()
        graph = await gb.build_graph()
    except Exception as exc:
        logger.error("Graph build failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"Graph build failed: {exc}") from exc

    # ── Get GNN output (regime / confidence) ──────────────────────────────
    regime = "sideways"
    confidence = 50.0
    try:
        from app.gnn.inference import GNNInference
        gnn = GNNInference()
        scores = await gnn.get_behavioral_scores()
        regime = scores.get("regime", "sideways")
        confidence = scores.get("confidence", 50.0)
    except Exception as exc:
        logger.warning("GNN inference skipped during graph export: %s", exc)

    # ── Build node list ────────────────────────────────────────────────────
    nodes: list[dict] = []
    # Maps (node_type, local_idx) → global node id string
    node_id_map: dict[tuple[str, int], str] = {}

    node_types_in_graph = [
        "exchange", "whale_wallet", "dex_pool",
        "retail_cluster", "news_source", "social_account", "on_chain_contract",
    ]

    for ntype in node_types_in_graph:
        try:
            x = graph[ntype].x  # shape [N, 16]
        except (KeyError, AttributeError):
            continue

        labels = _NODE_LABELS.get(ntype, [])
        color = _NODE_COLORS.get(ntype, "#94a3b8")
        group = _NODE_GROUPS.get(ntype, 0)

        for idx in range(x.shape[0]):
            feats = x[idx].tolist()
            nid = f"{ntype}_{idx}"
            node_id_map[(ntype, idx)] = nid

            nodes.append({
                "id":       nid,
                "type":     ntype,
                "label":    labels[idx] if idx < len(labels) else f"{ntype}-{idx}",
                "group":    group,
                "size":     _size_from_volume_rank(feats[7]),
                "color":    color,
                "metrics":  _extract_metrics(feats),
                "features": [round(f, 4) for f in feats],
            })

    # ── Build edge list ────────────────────────────────────────────────────
    edges: list[dict] = []

    for edge_key in graph.edge_types:
        src_type, rel_type, dst_type = edge_key
        edge_color = _EDGE_COLORS.get(rel_type, "#6b7280")
        try:
            ei = graph[src_type, rel_type, dst_type].edge_index  # [2, E]
        except (KeyError, AttributeError):
            continue

        if ei.shape[1] == 0:
            continue

        src_list = ei[0].tolist()
        dst_list = ei[1].tolist()
        for s, d in zip(src_list, dst_list):
            src_nid = node_id_map.get((src_type, s))
            dst_nid = node_id_map.get((dst_type, d))
            if src_nid is None or dst_nid is None:
                continue

            # Edge weight: average of volume_rank from both endpoints
            src_node = next((n for n in nodes if n["id"] == src_nid), None)
            dst_node = next((n for n in nodes if n["id"] == dst_nid), None)
            weight = 0.5
            if src_node and dst_node:
                weight = round(
                    (src_node["metrics"]["volume_rank"] + dst_node["metrics"]["volume_rank"]) / 2,
                    3,
                )

            edges.append({
                "source": src_nid,
                "target": dst_nid,
                "type":   rel_type,
                "weight": weight,
                "color":  edge_color,
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "regime":        regime,
            "gnn_confidence": confidence,
            "node_count":    len(nodes),
            "edge_count":    len(edges),
            "generated_at":  int(time.time()),
        },
    }


# ── Strategy 3-D graph ────────────────────────────────────────────────────────

def _pearson_r(a: list[float], b: list[float]) -> float:
    """Fast Pearson correlation between two equity curves."""
    n = min(len(a), len(b))
    if n < 3:
        return 0.0
    xs, ys = a[:n], b[:n]
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx  = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy  = math.sqrt(sum((y - my) ** 2 for y in ys))
    return round(num / (dx * dy), 4) if dx * dy > 0 else 0.0


def _regime_color(score: float) -> str:
    """Green (good fit) → amber → red (poor fit)."""
    if score >= 0.75:  return "#22c55e"
    if score >= 0.50:  return "#f59e0b"
    return "#ef4444"


def _combo_color(avg_pnl: float) -> str:
    if avg_pnl > 5:   return "#818cf8"
    if avg_pnl > 0:   return "#6366f1"
    return "#4f46e5"


_BEHAVIORAL_NODES = [
    {"id": "beh_fear_greed",  "name": "Fear & Greed",    "color": "#f472b6"},
    {"id": "beh_whale",       "name": "Whale Flow",       "color": "#60a5fa"},
    {"id": "beh_social",      "name": "Social Sentiment", "color": "#a78bfa"},
    {"id": "beh_news",        "name": "News Shock",       "color": "#fb923c"},
    {"id": "beh_accumulate",  "name": "Accumulation",     "color": "#34d399"},
]

# Which behavioral signal influences which strategy (weight 0–1)
_BEHAVIORAL_INFLUENCES: dict[str, list[tuple[str, float]]] = {
    "beh_fear_greed":  [("DCA", 0.8), ("HODL", 0.7), ("SCALPING", 0.5), ("FUTURES", 0.6)],
    "beh_whale":       [("SWING", 0.75), ("TREND_FOLLOWING", 0.7), ("ARBITRAGE", 0.6)],
    "beh_social":      [("NEWS_SENTIMENT", 0.9), ("DAY_TRADING", 0.65), ("SCALPING", 0.55)],
    "beh_news":        [("NEWS_SENTIMENT", 0.95), ("SWING", 0.6), ("FUTURES", 0.55)],
    "beh_accumulate":  [("DCA", 0.85), ("RANGE", 0.7), ("HODL", 0.65), ("DEFI_YIELD", 0.6)],
}

_REGIME_NODE_COLORS = {
    "bull":       "#22c55e",
    "bear":       "#ef4444",
    "sideways":   "#f59e0b",
    "transition": "#6b7280",
}


@router.get("/strategy-graph")
async def get_strategy_graph(asset: str = "BTC"):
    """
    3-D force graph of all 12 strategies + top synergy combos.

    Nodes
    ─────
    • strategy      — one per strategy, sized by |pnl_30d|, colored by regime fit
    • combo         — top-5 pairwise combos by synergy score
    • regime        — 4 regime nodes (current regime glows)
    • behavioral    — 5 behavioral signal drivers

    Links
    ─────
    • synergy       — between strategies: 1 − |pearsonR(equity_A, equity_B)|
                      (orthogonal = good diversification)
    • regime_fit    — strategy → regime node, weight = fit score
    • combo_member  — combo → each member strategy
    • beh_influence — behavioral node → strategy, weight = influence weight
    """
    from app.strategies import STRATEGY_REGISTRY
    from app.strategies.signal_engine import REGIME_SCORES, compute_performance
    from app.gnn.inference import GNNInference
    from app.main import _gnn_inference

    gnn: GNNInference = _gnn_inference or GNNInference()
    gnn_out   = await gnn.predict()
    scores    = await gnn.get_behavioral_scores()
    regime    = getattr(gnn_out, "regime", "sideways")
    regime_sc = REGIME_SCORES.get(regime, REGIME_SCORES["sideways"])

    # ── Fetch performance data ────────────────────────────────────────────────
    perf = await compute_performance(asset.upper(), gnn_out)
    strat_data = perf.get("strategies", {})
    prices_len = len(perf.get("prices", []))

    # active set (in-memory from strategies route)
    try:
        from app.api.routes.strategies import _active_strategies
    except Exception:
        _active_strategies = set()

    # ── Strategy nodes ────────────────────────────────────────────────────────
    nodes: list[dict] = []
    equities: dict[str, list[float]] = {}
    strat_meta: dict[str, dict] = {}

    REGIME_NAMES = list(REGIME_SCORES.keys())   # bull, bear, sideways, transition
    N = len(STRATEGY_REGISTRY)
    for i, (name, cls) in enumerate(STRATEGY_REGISTRY.items()):
        sd = strat_data.get(name, {})
        pnl        = sd.get("total_return", 0.0)
        win_rate   = sd.get("win_rate", 0.0)
        equity     = sd.get("equity", [])
        fit        = regime_sc.get(name, 0.5)
        is_active  = name in _active_strategies

        # arrange in a ring
        angle = (i / N) * 2 * math.pi
        radius = 120
        x = round(radius * math.cos(angle), 1)
        z = round(radius * math.sin(angle), 1)
        y = round(pnl * 1.5, 1)   # vertical axis = performance

        equities[name] = equity
        strat_meta[name] = {"pnl": pnl, "fit": fit, "win_rate": win_rate}

        nodes.append({
            "id":          name,
            "name":        cls.display_name,
            "type":        "strategy",
            "group":       0,
            "val":         max(3, min(20, 5 + abs(pnl) * 0.8)),
            "color":       "#818cf8" if is_active else _regime_color(fit),
            "pnl_30d":     round(pnl, 2),
            "win_rate":    round(win_rate, 1),
            "regime_score": round(fit * 100, 1),
            "is_active":   is_active,
            "description": cls.description,
            "fx": x, "fy": y, "fz": z,
        })

    # ── Compute pairwise equity correlations ──────────────────────────────────
    strat_names = list(STRATEGY_REGISTRY.keys())
    corr_matrix: dict[tuple[str, str], float] = {}
    for i in range(len(strat_names)):
        for j in range(i + 1, len(strat_names)):
            a, b = strat_names[i], strat_names[j]
            ea, eb = equities.get(a, []), equities.get(b, [])
            r = _pearson_r(ea, eb) if ea and eb else 0.0
            corr_matrix[(a, b)] = r

    # ── Top combo nodes (best synergy = high avg pnl + low correlation) ───────
    combo_scores: list[tuple[float, str, str]] = []
    for (a, b), r in corr_matrix.items():
        pa = strat_meta[a]["pnl"]
        pb = strat_meta[b]["pnl"]
        avg_pnl   = (pa + pb) / 2
        synergy   = (1 - abs(r)) * max(0.01, avg_pnl + 10) / 10  # diversification × profit
        combo_scores.append((synergy, a, b))
    combo_scores.sort(reverse=True)

    top_combos = combo_scores[:5]
    combo_equity_lookup: dict[str, list[float]] = {}

    for rank, (syn, a, b) in enumerate(top_combos):
        ea = equities.get(a, [])
        eb = equities.get(b, [])
        n  = min(len(ea), len(eb))
        combo_eq = [(ea[i] + eb[i]) / 2 for i in range(n)] if n > 0 else []
        combo_pnl = combo_eq[-1] if combo_eq else 0.0
        combo_id  = f"COMBO_{a}_{b}"
        combo_equity_lookup[combo_id] = combo_eq

        # Position combos in an inner ring above strategies
        angle  = rank * 2 * math.pi / len(top_combos)
        radius = 55
        nodes.append({
            "id":          combo_id,
            "name":        f"{STRATEGY_REGISTRY[a].display_name} + {STRATEGY_REGISTRY[b].display_name}",
            "type":        "combo",
            "group":       1,
            "val":         max(6, min(25, 8 + abs(combo_pnl) * 0.6)),
            "color":       _combo_color(combo_pnl),
            "pnl_30d":     round(combo_pnl, 2),
            "synergy":     round(syn, 3),
            "correlation": round(corr_matrix.get((a, b), corr_matrix.get((b, a), 0)), 3),
            "members":     [a, b],
            "fx": round(radius * math.cos(angle), 1),
            "fy": round(combo_pnl * 1.5 + 20, 1),
            "fz": round(radius * math.sin(angle), 1),
        })

    # ── Regime nodes ─────────────────────────────────────────────────────────
    regime_positions = [
        (160, 80, 0), (-160, 80, 0), (0, 80, 160), (0, 80, -160)
    ]
    for ri, (rname, (rx, ry, rz)) in enumerate(zip(REGIME_NAMES, regime_positions)):
        nodes.append({
            "id":       f"regime_{rname}",
            "name":     rname.capitalize(),
            "type":     "regime",
            "group":    2,
            "val":      10 if rname == regime else 6,
            "color":    _REGIME_NODE_COLORS.get(rname, "#6b7280"),
            "current":  rname == regime,
            "fx": rx, "fy": ry, "fz": rz,
        })

    # ── Behavioral signal nodes ───────────────────────────────────────────────
    score_map = {
        "beh_fear_greed": scores.get("greed_score", 50) / 100,
        "beh_whale":      0.5,
        "beh_social":     scores.get("greed_score", 50) / 100,
        "beh_news":       scores.get("news_shock_score", 50) / 100,
        "beh_accumulate": scores.get("accumulation_score", 50) / 100,
    }
    for bi, bnode in enumerate(_BEHAVIORAL_NODES):
        angle  = bi * 2 * math.pi / len(_BEHAVIORAL_NODES)
        radius = 220
        nodes.append({
            **bnode,
            "type":  "behavioral",
            "group": 3,
            "val":   max(4, round(score_map.get(bnode["id"], 0.5) * 12, 1)),
            "score": round(score_map.get(bnode["id"], 0.5) * 100, 1),
            "fx": round(radius * math.cos(angle), 1),
            "fy": 0.0,
            "fz": round(radius * math.sin(angle), 1),
        })

    # ── Links ─────────────────────────────────────────────────────────────────
    links: list[dict] = []

    # Strategy ↔ strategy synergy (only show meaningful ones: abs_r < 0.6 or both pnl > 0)
    for (a, b), r in corr_matrix.items():
        pa = strat_meta[a]["pnl"]
        pb = strat_meta[b]["pnl"]
        if abs(r) < 0.5 or (pa > 0 and pb > 0):
            links.append({
                "source":  a,
                "target":  b,
                "value":   round(1 - abs(r), 3),   # thickness = diversification
                "type":    "synergy",
                "color":   "#22c55e" if r < 0.2 else "#6b7280",
                "label":   f"r={r:.2f}",
            })

    # Combo → member
    for node in nodes:
        if node["type"] != "combo":
            continue
        for member in node.get("members", []):
            links.append({
                "source": node["id"],
                "target": member,
                "value":  2,
                "type":   "combo_member",
                "color":  "#818cf8",
            })

    # Strategy → regime fit (only the current regime)
    for name in STRATEGY_REGISTRY:
        fit = regime_sc.get(name, 0.5)
        if fit >= 0.5:   # only show meaningful fits
            links.append({
                "source": name,
                "target": f"regime_{regime}",
                "value":  round(fit * 3, 2),
                "type":   "regime_fit",
                "color":  _regime_color(fit),
                "label":  f"{round(fit*100)}%",
            })

    # Behavioral → strategy influence
    for beh_id, influences in _BEHAVIORAL_INFLUENCES.items():
        for strat_name, weight in influences:
            if strat_name in STRATEGY_REGISTRY:
                links.append({
                    "source": beh_id,
                    "target": strat_name,
                    "value":  round(weight * 2, 2),
                    "type":   "beh_influence",
                    "color":  next(
                        (n["color"] for n in _BEHAVIORAL_NODES if n["id"] == beh_id), "#6b7280"
                    ),
                })

    return {
        "nodes": nodes,
        "links": links,
        "meta": {
            "asset":          asset.upper(),
            "regime":         regime,
            "gnn_confidence": round(scores.get("confidence", 50), 1),
            "node_count":     len(nodes),
            "link_count":     len(links),
            "generated_at":   int(time.time()),
        },
    }
