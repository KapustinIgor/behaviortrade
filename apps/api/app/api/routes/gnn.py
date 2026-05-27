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
