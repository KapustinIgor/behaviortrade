from __future__ import annotations

"""
BehaviorGAT Trainer — Phase 2/3.

Collects (graph_snapshot, price_outcome) pairs every 30 min.
Runs a nightly full retrain and saves a checkpoint.

Loss = 0.4*BCE(dir_1h) + 0.3*BCE(dir_4h) + 0.2*BCE(dir_24h) + 0.1*CE(regime)
"""

import json
import logging
import time
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

from app.gnn.graph_builder import GraphBuilder
from app.gnn.model import BehaviorGAT, REGIME_CLASSES

logger = logging.getLogger(__name__)

SAMPLE_KEY   = "gnn_training_samples"
MAX_SAMPLES  = 500
BATCH_SIZE   = 16
EPOCHS       = 30
LR           = 1e-3
WEIGHT_DECAY = 1e-4

_REGIME_IDX = {r: i for i, r in enumerate(REGIME_CLASSES)}


class GNNTrainer:
    def __init__(self, model_path: str) -> None:
        self._model_path = Path(model_path)
        self._device = torch.device("cpu")  # MPS slower than CPU for sparse hetero GATConv
        self._gb = GraphBuilder()

    # ── Sample collection ─────────────────────────────────────────────────

    async def collect_sample(self) -> None:
        """Snapshot the current graph features into the training buffer."""
        from app.core.redis_client import get_json, get_redis

        try:
            graph = await self._gb.build_graph()
            fg    = await get_json("fear_greed_latest") or {}
            p_btc = await get_json("price:bitcoin")     or {}
            p_eth = await get_json("price:ethereum")    or {}

            sample = {
                "ts":         int(time.time()),
                "fg_value":   fg.get("value", 50),
                "btc_price":  p_btc.get("price", 0.0),
                "eth_price":  p_eth.get("price", 0.0),
                "btc_change": p_btc.get("change_24h", 0.0),
                "exchange_x": graph["exchange"].x.tolist(),
                "whale_x":    graph["whale_wallet"].x[:5].tolist(),
            }
            r = await get_redis()
            await r.lpush(SAMPLE_KEY, json.dumps(sample))
            await r.ltrim(SAMPLE_KEY, 0, MAX_SAMPLES - 1)
            count = await r.llen(SAMPLE_KEY)
            logger.info("GNN sample collected (buffer: %d/%d)", count, MAX_SAMPLES)
        except Exception as e:
            logger.warning("GNN sample collection failed: %s", e)

    # ── Nightly retrain ───────────────────────────────────────────────────

    async def full_retrain(self, days: int = 90) -> None:
        """Load sample buffer, retrain BehaviorGAT, save best checkpoint."""
        from app.core.redis_client import get_redis

        r       = await get_redis()
        raw     = await r.lrange(SAMPLE_KEY, 0, -1)
        samples = [json.loads(s) for s in raw]

        if len(samples) < 20:
            logger.info("Not enough GNN samples (%d < 20) — skipping retrain", len(samples))
            return

        logger.info("GNN retrain: %d samples on %s", len(samples), self._device)

        model = BehaviorGAT().to(self._device)
        if self._model_path.exists():
            ckpt = torch.load(str(self._model_path), map_location=self._device, weights_only=True)
            model.load_state_dict(ckpt["model_state_dict"])
            logger.info("Resumed from existing checkpoint")

        optimizer = optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
        scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)
        bce = nn.BCELoss()
        ce  = nn.CrossEntropyLoss()

        model.train()
        best_loss  = float("inf")
        best_state = None

        for epoch in range(1, EPOCHS + 1):
            epoch_loss, count = 0.0, 0

            for i in range(0, len(samples) - 1, BATCH_SIZE):
                batch = samples[i : i + BATCH_SIZE]

                for s in batch:
                    try:
                        graph = self._graph_from_sample(s).to(self._device)
                        next_s = samples[min(samples.index(s) + 1, len(samples) - 1)]

                        btc_now  = s.get("btc_price", 1.0) or 1.0
                        btc_next = next_s.get("btc_price", btc_now)
                        dir_true = 1.0 if btc_next > btc_now else 0.0
                        fg_v     = s.get("fg_value", 50) / 100.0
                        regime_true = _REGIME_IDX[
                            "bull" if fg_v > 0.65 else "bear" if fg_v < 0.35 else "sideways"
                        ]

                        t_dir = torch.tensor([[dir_true]], dtype=torch.float32, device=self._device)
                        t_reg = torch.tensor([regime_true], dtype=torch.long,  device=self._device)

                        optimizer.zero_grad()
                        mkt, news_emb = self._forward_to_embeddings(model, graph)

                        l_d1  = bce(model.dir_1h_head(mkt),  t_dir)
                        l_d4  = bce(model.dir_4h_head(mkt),  t_dir)
                        l_d24 = bce(model.dir_24h_head(mkt), t_dir)
                        l_reg = ce(model.regime_head(mkt), t_reg)

                        loss = 0.4 * l_d1 + 0.3 * l_d4 + 0.2 * l_d24 + 0.1 * l_reg
                        loss.backward()
                        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                        optimizer.step()

                        epoch_loss += loss.item()
                        count += 1
                    except Exception as e:
                        logger.debug("Training step skipped: %s", e)

            scheduler.step()
            avg = epoch_loss / max(count, 1)
            if avg < best_loss:
                best_loss  = avg
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
            if epoch % 5 == 0:
                logger.info("epoch %d/%d  loss=%.4f  best=%.4f", epoch, EPOCHS, avg, best_loss)

        if best_state is not None:
            self._model_path.parent.mkdir(parents=True, exist_ok=True)
            torch.save({
                "model_state_dict": best_state,
                "epoch": EPOCHS,
                "val_loss": round(best_loss, 6),
                "regime_classes": REGIME_CLASSES,
            }, str(self._model_path))
            logger.info("Checkpoint saved → %s  (best_loss=%.4f)", self._model_path, best_loss)

    # Kept for backwards compatibility
    async def hourly_finetune(self) -> None:
        await self.collect_sample()

    def save_checkpoint(self, path: str | None = None) -> None:
        raise NotImplementedError("Use full_retrain() which saves automatically")

    def load_checkpoint(self, path: str | None = None) -> None:
        raise NotImplementedError("Use GNNInference.load_model() instead")

    # ── Internal helpers ──────────────────────────────────────────────────

    @staticmethod
    def _forward_to_embeddings(model: BehaviorGAT, graph) -> tuple[torch.Tensor, torch.Tensor]:
        """Run conv layers and return (market_emb, news_emb) with gradient tracking."""
        x_raw = {nt: graph[nt].x for nt in graph.node_types if hasattr(graph[nt], "x")}
        x_emb = {nt: model.node_embed[nt](x) for nt, x in x_raw.items() if nt in model.node_embed}
        ei = {et: graph[et].edge_index for et in graph.edge_types
              if hasattr(graph[et], "edge_index") and graph[et].edge_index.shape[1] > 0}

        x1_out = model.conv1(x_emb, ei) if ei else {}
        x1 = {nt: F.elu(x1_out[nt] + x_emb[nt]) if nt in x1_out else F.elu(x_emb[nt]) for nt in x_emb}
        x2_out = model.conv2(x1, ei) if ei else {}
        x2 = {nt: F.elu(x2_out[nt]) if nt in x2_out else F.elu(model.proj2[nt](x1[nt])) for nt in x1}

        exch = x2.get("exchange")
        mkt  = exch.mean(dim=0, keepdim=True) if exch is not None else \
               torch.cat(list(x2.values())).mean(dim=0, keepdim=True)
        news = x2.get("news_source", mkt)
        return mkt, news.mean(dim=0, keepdim=True)

    @staticmethod
    def _graph_from_sample(sample: dict):
        from torch_geometric.data import HeteroData

        g = HeteroData()
        ex_x = sample.get("exchange_x")
        g["exchange"].x = torch.tensor(ex_x, dtype=torch.float32) if ex_x \
                          else torch.zeros((10, 16))

        wh_x = sample.get("whale_x")
        if wh_x:
            base = torch.tensor(wh_x, dtype=torch.float32)
            pad  = torch.zeros((20 - base.shape[0], 16))
            g["whale_wallet"].x = torch.cat([base, pad], dim=0)
        else:
            g["whale_wallet"].x = torch.zeros((20, 16))

        fg = sample.get("fg_value", 50) / 100.0
        g["dex_pool"].x          = torch.full((5,  16), fg)
        g["retail_cluster"].x    = torch.full((5,  16), fg)
        g["news_source"].x       = torch.full((5,  16), fg)
        g["social_account"].x    = torch.full((5,  16), fg)
        g["on_chain_contract"].x = torch.full((3,  16), fg)

        # Dense exchange ↔ exchange edges (always present)
        n = 10
        src = [i for i in range(n) for j in range(n) if i != j]
        dst = [j for i in range(n) for j in range(n) if i != j]
        g["exchange", "trade_volume", "exchange"].edge_index = \
            torch.tensor([src, dst], dtype=torch.long)

        return g
