from __future__ import annotations

"""
HistoricalTrainer — trains BehaviorGAT from 1 year of Binance OHLCV data.

Usage (from apps/api/):
    python -m scripts.train_historical [--days 365] [--epochs 50] [--step-hours 4]

Steps:
  1. Fetch / load cached Binance klines + Alternative.me Fear & Greed
  2. Build HeteroData graphs for every `step_hours`-th snapshot
  3. Train BehaviorGAT with direction + regime labels
  4. Save best checkpoint to MODEL_PATH
"""

import asyncio
import logging
import math
from pathlib import Path
from typing import NamedTuple

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch_geometric.data import HeteroData

from app.gnn.graph_builder import GraphBuilder, _change_to_feature, _clamp01, _stable_noise
from app.gnn.historical_data import (
    build_aligned_timestamps,
    labels_at,
    load_or_fetch,
    price_features_at,
)
from app.gnn.model import BehaviorGAT, REGIME_CLASSES

logger = logging.getLogger(__name__)

_REGIME_IDX = {r: i for i, r in enumerate(REGIME_CLASSES)}

EPOCHS       = 50
LR           = 3e-4
WEIGHT_DECAY = 1e-4
BATCH_SIZE   = 32


# ── Synchronous graph builder from price snapshot ──────────────────────────────

_GB = GraphBuilder()


def build_graph_from_snapshot(
    prices: dict[str, dict],
    fg_value: float,
) -> HeteroData:
    """
    Build a HeteroData graph from a historical price snapshot.
    No Redis / async required — pure CPU computation.
    """
    # Convert price_features_at() output to the format _build_exchange_features expects
    redis_style: dict[str, dict] = {}
    for coin, p in prices.items():
        redis_style[coin] = {
            "price":      p["price"],
            "change_24h": p["change_24h"],
        }

    data = HeteroData()
    data["whale_wallet"].x      = _GB._build_whale_features(fg_value, [], redis_style)
    data["exchange"].x          = _GB._build_exchange_features(fg_value, redis_style)
    data["dex_pool"].x          = _GB._build_dex_features(fg_value, redis_style)
    data["retail_cluster"].x    = _GB._build_retail_features(fg_value)
    data["news_source"].x       = _GB._build_news_features(fg_value, [])
    data["social_account"].x    = _GB._build_social_features(fg_value)
    data["on_chain_contract"].x = _GB._build_contract_features(fg_value)

    n_whale    = data["whale_wallet"].x.shape[0]
    n_exchange = data["exchange"].x.shape[0]
    n_dex      = data["dex_pool"].x.shape[0]
    n_news     = data["news_source"].x.shape[0]
    n_social   = data["social_account"].x.shape[0]

    data["whale_wallet",  "fund_flow",              "exchange"      ].edge_index = \
        _GB._whale_to_exchange_edges(n_whale, n_exchange, [])
    data["exchange",      "fund_flow",              "whale_wallet"  ].edge_index = \
        _GB._exchange_to_whale_edges(n_exchange, n_whale)
    data["exchange",      "trade_volume",           "exchange"      ].edge_index = \
        _GB._full_bipartite_edges(n_exchange, n_exchange, exclude_self=True)
    data["social_account","social_influence",       "social_account"].edge_index = \
        _GB._ring_edges(n_social)
    data["news_source",   "news_citation",          "news_source"   ].edge_index = \
        _GB._news_citation_edges(n_news, [])
    data["whale_wallet",  "liquidity_provision",    "dex_pool"      ].edge_index = \
        _GB._whale_to_dex_edges(n_whale, n_dex)
    data["whale_wallet",  "historical_correlation", "whale_wallet"  ].edge_index = \
        _GB._historical_corr_edges(n_whale, fg_value)
    data["exchange",      "historical_correlation", "dex_pool"      ].edge_index = \
        _GB._exchange_to_dex_corr_edges(n_exchange, n_dex)

    return data


# ── Sample dataclass ───────────────────────────────────────────────────────────

class Sample(NamedTuple):
    graph:    HeteroData
    dir_1h:   float
    dir_4h:   float
    dir_24h:  float
    regime:   int


# ── Main trainer ───────────────────────────────────────────────────────────────

class HistoricalTrainer:
    def __init__(self, model_path: str) -> None:
        self._model_path = Path(model_path)
        self._device     = torch.device("cpu")

    async def train(
        self,
        days:       int = 365,
        epochs:     int = EPOCHS,
        step_hours: int = 4,
    ) -> None:
        data = await load_or_fetch(days)
        timestamps = build_aligned_timestamps(data, step_hours)
        logger.info("Aligned timestamps: %d  (every %dh over %d days)",
                    len(timestamps), step_hours, days)

        # ── Build samples ──────────────────────────────────────────────────
        logger.info("Building graph snapshots (this may take a minute)...")
        samples: list[Sample] = []

        for i, ts in enumerate(timestamps):
            lbls = labels_at(data, ts)
            if lbls is None:
                continue
            pf   = price_features_at(data, ts)
            if not pf:
                continue
            fg_v = data["fg"].get(ts, data["fg"].get(ts - (ts % 3600), 50)) / 100.0
            graph = build_graph_from_snapshot(pf, fg_v)
            samples.append(Sample(
                graph   = graph,
                dir_1h  = float(lbls["dir_1h"]),
                dir_4h  = float(lbls["dir_4h"]),
                dir_24h = float(lbls["dir_24h"]),
                regime  = _REGIME_IDX.get(lbls["regime"], 2),
            ))

            if (i + 1) % 500 == 0:
                logger.info("  Built %d / %d snapshots", i + 1, len(timestamps))

        logger.info("Total training samples: %d", len(samples))
        if len(samples) < 50:
            logger.error("Not enough samples — aborting")
            return

        # ── Label balance ─────────────────────────────────────────────────
        up1h = sum(1 for s in samples if s.dir_1h == 1.0) / len(samples)
        up24h = sum(1 for s in samples if s.dir_24h == 1.0) / len(samples)
        logger.info("Label balance — up_1h: %.1f%%  up_24h: %.1f%%", up1h * 100, up24h * 100)

        # ── Model + optimiser ─────────────────────────────────────────────
        model = BehaviorGAT().to(self._device)
        if self._model_path.exists():
            ckpt = torch.load(str(self._model_path), map_location=self._device, weights_only=True)
            model.load_state_dict(ckpt["model_state_dict"])
            logger.info("Resumed from existing checkpoint at %s", self._model_path)

        optimizer = optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
        scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
        bce = nn.BCELoss()
        ce  = nn.CrossEntropyLoss()

        best_loss  = float("inf")
        best_state = None

        # ── Training loop ─────────────────────────────────────────────────
        for epoch in range(1, epochs + 1):
            model.train()
            epoch_loss, count = 0.0, 0

            for i in range(0, len(samples), BATCH_SIZE):
                batch = samples[i : i + BATCH_SIZE]
                for s in batch:
                    try:
                        graph = s.graph.to(self._device)
                        t_d1  = torch.tensor([[s.dir_1h]],  dtype=torch.float32, device=self._device)
                        t_d4  = torch.tensor([[s.dir_4h]],  dtype=torch.float32, device=self._device)
                        t_d24 = torch.tensor([[s.dir_24h]], dtype=torch.float32, device=self._device)
                        t_reg = torch.tensor([s.regime],    dtype=torch.long,    device=self._device)

                        optimizer.zero_grad()
                        mkt, _ = _forward_embeddings(model, graph)

                        loss = (
                            0.4 * bce(model.dir_1h_head(mkt),  t_d1)
                          + 0.3 * bce(model.dir_4h_head(mkt),  t_d4)
                          + 0.2 * bce(model.dir_24h_head(mkt), t_d24)
                          + 0.1 * ce(model.regime_head(mkt),   t_reg)
                        )
                        loss.backward()
                        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                        optimizer.step()

                        epoch_loss += loss.item()
                        count      += 1
                    except Exception as e:
                        logger.debug("Step skipped: %s", e)

            scheduler.step()
            avg = epoch_loss / max(count, 1)
            if avg < best_loss:
                best_loss  = avg
                best_state = {k: v.clone() for k, v in model.state_dict().items()}

            if epoch % 5 == 0 or epoch == 1:
                logger.info("epoch %3d/%d  loss=%.5f  best=%.5f  lr=%.2e",
                            epoch, epochs, avg, best_loss,
                            optimizer.param_groups[0]["lr"])

        # ── Save checkpoint ───────────────────────────────────────────────
        if best_state is not None:
            self._model_path.parent.mkdir(parents=True, exist_ok=True)
            torch.save({
                "model_state_dict": best_state,
                "epoch":            epochs,
                "val_loss":         round(best_loss, 6),
                "regime_classes":   REGIME_CLASSES,
                "trained_on":       f"{len(samples)} historical samples ({days}d)",
            }, str(self._model_path))
            logger.info("Checkpoint saved → %s  (best_loss=%.5f)", self._model_path, best_loss)


# ── Internal helper (same pattern as trainer.py) ──────────────────────────────

def _forward_embeddings(model: BehaviorGAT, graph: HeteroData):
    x_raw = {nt: graph[nt].x for nt in graph.node_types if hasattr(graph[nt], "x")}
    x_emb = {nt: model.node_embed[nt](x) for nt, x in x_raw.items() if nt in model.node_embed}
    ei = {
        et: graph[et].edge_index
        for et in graph.edge_types
        if hasattr(graph[et], "edge_index") and graph[et].edge_index.shape[1] > 0
    }
    x1_out = model.conv1(x_emb, ei) if ei else {}
    x1 = {nt: F.elu(x1_out[nt] + x_emb[nt]) if nt in x1_out else F.elu(x_emb[nt]) for nt in x_emb}
    x2_out = model.conv2(x1, ei) if ei else {}
    x2 = {nt: F.elu(x2_out[nt]) if nt in x2_out else F.elu(model.proj2[nt](x1[nt])) for nt in x1}

    exch = x2.get("exchange")
    mkt  = exch.mean(dim=0, keepdim=True) if exch is not None else \
           torch.cat(list(x2.values()), dim=0).mean(dim=0, keepdim=True)
    news = x2.get("news_source", mkt)
    return mkt, news.mean(dim=0, keepdim=True)
