from __future__ import annotations

"""
BehaviorGAT — Heterogeneous Graph Attention Network for crypto behavioral prediction.

Architecture:
  node_embed  : per-node-type Linear(INPUT_DIM → HIDDEN_DIM_1) projection
  conv1       : HeteroConv(GATConv, 8 heads) → HIDDEN_DIM_1-dim embeddings
  conv2       : HeteroConv(GATConv, 4 heads) → HIDDEN_DIM_2-dim embeddings
  proj2       : per-node-type Linear(HIDDEN_DIM_1 → HIDDEN_DIM_2) fallback projection
  heads       : 10 independent prediction heads over mean-pooled exchange embeddings

Node types  : whale_wallet, exchange, dex_pool, retail_cluster,
              news_source, social_account, on_chain_contract
Edge types  : fund_flow, trade_volume, social_influence, news_citation,
              liquidity_provision, historical_correlation
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATConv, HeteroConv
from torch_geometric.data import HeteroData

from app.gnn.outputs import GNNOutput

REGIME_CLASSES = ["bull", "bear", "sideways", "transition"]

NODE_TYPES = [
    "whale_wallet", "exchange", "dex_pool",
    "retail_cluster", "news_source", "social_account", "on_chain_contract",
]

EDGE_TYPES: list[tuple[str, str, str]] = [
    ("whale_wallet",    "fund_flow",              "exchange"),
    ("exchange",        "fund_flow",              "whale_wallet"),
    ("exchange",        "trade_volume",           "exchange"),
    ("social_account",  "social_influence",       "social_account"),
    ("news_source",     "news_citation",          "news_source"),
    ("whale_wallet",    "liquidity_provision",    "dex_pool"),
    ("whale_wallet",    "historical_correlation", "whale_wallet"),
    ("exchange",        "historical_correlation", "dex_pool"),
]

INPUT_DIM   = 16
HIDDEN_DIM_1 = 128   # after conv1  (8 heads × 16)
HIDDEN_DIM_2 = 64    # after conv2  (4 heads × 16)
GAT_HEADS_1  = 8
GAT_HEADS_2  = 4


class BehaviorGAT(nn.Module):
    def __init__(self, in_dim: int = INPUT_DIM) -> None:
        super().__init__()

        # Project every node type to a common HIDDEN_DIM_1 space before message passing
        self.node_embed = nn.ModuleDict({
            nt: nn.Linear(in_dim, HIDDEN_DIM_1) for nt in NODE_TYPES
        })

        # Conv1: aggregate 1-hop neighborhood
        self.conv1 = HeteroConv(
            {
                et: GATConv(HIDDEN_DIM_1, HIDDEN_DIM_1 // GAT_HEADS_1,
                            heads=GAT_HEADS_1, add_self_loops=False)
                for et in EDGE_TYPES
            },
            aggr="sum",
        )

        # Conv2: 2-hop propagation
        self.conv2 = HeteroConv(
            {
                et: GATConv(HIDDEN_DIM_1, HIDDEN_DIM_2 // GAT_HEADS_2,
                            heads=GAT_HEADS_2, add_self_loops=False)
                for et in EDGE_TYPES
            },
            aggr="mean",
        )

        # Fallback projection for node types not updated by conv2
        self.proj2 = nn.ModuleDict({
            nt: nn.Linear(HIDDEN_DIM_1, HIDDEN_DIM_2) for nt in NODE_TYPES
        })

        # Prediction heads — all take the 64-dim market embedding
        def head(hidden: int = 32) -> nn.Sequential:
            return nn.Sequential(
                nn.Linear(HIDDEN_DIM_2, hidden), nn.ReLU(),
                nn.Linear(hidden, 1), nn.Sigmoid(),
            )

        self.panic_head      = head(32)
        self.greed_head      = head(32)
        self.accum_head      = head(32)
        self.distrib_head    = head(32)
        self.confidence_head = head(16)
        self.news_shock_head = head(16)
        self.dir_1h_head     = head(32)
        self.dir_4h_head     = head(32)
        self.dir_24h_head    = head(32)
        # regime: 4-class softmax
        self.regime_head = nn.Sequential(
            nn.Linear(HIDDEN_DIM_2, 32), nn.ReLU(), nn.Linear(32, 4),
        )

    def forward(self, data: HeteroData) -> GNNOutput:
        # ── 1. Collect raw node features ───────────────────────────────────
        x_raw = {nt: data[nt].x for nt in data.node_types if hasattr(data[nt], "x")}

        # ── 2. Project every node type to HIDDEN_DIM_1 ─────────────────────
        x_emb: dict[str, torch.Tensor] = {
            nt: self.node_embed[nt](x) for nt, x in x_raw.items() if nt in self.node_embed
        }

        # Only keep edge types that exist in this graph and have at least one edge
        ei = {
            et: data[et].edge_index
            for et in data.edge_types
            if hasattr(data[et], "edge_index") and data[et].edge_index.shape[1] > 0
        }

        # ── 3. Conv1 + residual ────────────────────────────────────────────
        x1_out = self.conv1(x_emb, ei) if ei else {}
        x1: dict[str, torch.Tensor] = {
            nt: F.elu(x1_out[nt] + x_emb[nt]) if nt in x1_out else F.elu(x_emb[nt])
            for nt in x_emb
        }

        # ── 4. Conv2 + fallback projection ────────────────────────────────
        x2_out = self.conv2(x1, ei) if ei else {}
        x2: dict[str, torch.Tensor] = {
            nt: F.elu(x2_out[nt]) if nt in x2_out else F.elu(self.proj2[nt](x1[nt]))
            for nt in x1
        }

        # ── 5. Market embedding: mean-pool exchange nodes ─────────────────
        exch = x2.get("exchange")
        market_emb = (
            exch.mean(dim=0, keepdim=True)
            if exch is not None and exch.shape[0] > 0
            else torch.cat(list(x2.values()), dim=0).mean(dim=0, keepdim=True)
        )  # [1, 64]

        # News embedding: mean-pool news_source nodes
        news_nodes = x2.get("news_source", market_emb)
        news_emb = news_nodes.mean(dim=0, keepdim=True)

        # ── 6. Prediction heads ───────────────────────────────────────────
        regime_idx = int(self.regime_head(market_emb).softmax(dim=-1).argmax(dim=-1).item())
        regime = REGIME_CLASSES[regime_idx]

        return GNNOutput(
            panic_score      = round(self.panic_head(market_emb).item(),      4),
            greed_score      = round(self.greed_head(market_emb).item(),      4),
            accumulation_score = round(self.accum_head(market_emb).item(),    4),
            distribution_score = round(self.distrib_head(market_emb).item(), 4),
            regime           = regime,
            confidence       = round(self.confidence_head(market_emb).item(), 4),
            direction_1h     = round(self.dir_1h_head(market_emb).item(),     4),
            direction_4h     = round(self.dir_4h_head(market_emb).item(),     4),
            direction_24h    = round(self.dir_24h_head(market_emb).item(),    4),
            news_shock_score = round(self.news_shock_head(news_emb).item(),   4),
        )
