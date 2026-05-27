from __future__ import annotations

import logging
from pathlib import Path

import torch

from app.gnn.outputs import GNNOutput

logger = logging.getLogger(__name__)


class GNNInference:
    """
    Phase 1: mock scores derived from fear/greed + news sentiment.
    Phase 2: real BehaviorGAT inference — activated when a checkpoint exists at MODEL_PATH.
    Phase 3: live retraining updates the checkpoint nightly.
    """

    def __init__(self) -> None:
        self._model: "BehaviorGAT | None" = None  # type: ignore[name-defined]
        self._graph_builder: "GraphBuilder | None" = None  # type: ignore[name-defined]
        # CPU outperforms MPS for this graph size (sparse hetero GATConv)
        self._device: torch.device = torch.device("cpu")

    async def load_model(self, model_path: str) -> bool:
        """Load checkpoint if it exists. Returns True on success."""
        p = Path(model_path)
        if not p.exists():
            logger.info("No GNN checkpoint at %s — using mock scores (Phase 1)", model_path)
            return False
        try:
            from app.gnn.model import BehaviorGAT
            from app.gnn.graph_builder import GraphBuilder

            model = BehaviorGAT().to(self._device)
            ckpt = torch.load(str(p), map_location=self._device, weights_only=True)
            model.load_state_dict(ckpt["model_state_dict"])
            model.eval()
            self._model = model
            self._graph_builder = GraphBuilder()
            epoch = ckpt.get("epoch", "?")
            val_loss = ckpt.get("val_loss", "?")
            logger.info("BehaviorGAT loaded from %s (epoch=%s, val_loss=%s)", p, epoch, val_loss)
            return True
        except Exception as e:
            logger.error("Failed to load GNN checkpoint: %s", e)
            self._model = None
            return False

    async def predict(self, graph_data=None) -> GNNOutput:
        if self._model is None:
            return await self._mock_scores()

        try:
            if graph_data is None and self._graph_builder:
                graph_data = await self._graph_builder.build_graph()
                graph_data = graph_data.to(self._device)

            with torch.no_grad():
                output = self._model.forward(graph_data)
            return output
        except Exception as e:
            logger.warning("GNN forward pass failed (%s) — falling back to mock", e)
            return await self._mock_scores()

    async def get_behavioral_scores(self) -> dict:
        output = await self.predict()
        return {
            "panic_score":         round(output.panic_score * 100,          1),
            "greed_score":         round(output.greed_score * 100,          1),
            "accumulation_score":  round(output.accumulation_score * 100,   1),
            "distribution_score":  round(output.distribution_score * 100,   1),
            "regime":              output.regime,
            "confidence":          round(output.confidence * 100,           1),
            "news_shock_score":    round(output.news_shock_score * 100,     1),
            "direction_1h":        round(output.direction_1h * 100,         1),
            "direction_4h":        round(output.direction_4h * 100,         1),
            "direction_24h":       round(output.direction_24h * 100,        1),
        }

    async def build_and_run(self) -> tuple[GNNOutput, object]:
        """Build the graph, run a forward pass (real or mock), return (output, graph).
        Used by the trainer to collect training samples."""
        from app.gnn.graph_builder import GraphBuilder
        gb = self._graph_builder or GraphBuilder()
        graph = await gb.build_graph()
        if self._model is not None:
            graph_dev = graph.to(self._device)
            with torch.no_grad():
                output = self._model.forward(graph_dev)
        else:
            output = await self._mock_scores()
        return output, graph

    # ── Phase 1 mock (fear/greed + news derived) ──────────────────────────

    async def _mock_scores(self) -> GNNOutput:
        from app.core.redis_client import get_json

        fg = await get_json("fear_greed_latest") or {}
        fg_value = fg.get("value", 50) / 100.0

        news_shock = 0.2
        try:
            news = await get_json("news_latest") or []
            if news:
                scores = [abs(item.get("sentiment_score", 0.0)) for item in news]
                news_shock = min(1.0, sum(scores) / len(scores) * 2)
        except Exception:
            pass

        panic  = round(max(0.0, min(1.0, 0.6 - fg_value)), 3)
        greed  = round(min(1.0, fg_value), 3)
        accum  = round(min(1.0, 0.2 + (1 - panic) * 0.4), 3)
        distrib = round(min(1.0, 0.1 + greed * 0.45), 3)
        confidence = round(min(1.0, 0.5 + abs(fg_value - 0.5) * 0.4), 3)

        regime = "sideways"
        if greed > 0.65:
            regime = "bull"
        elif panic > 0.45:
            regime = "bear"

        return GNNOutput(
            panic_score        = panic,
            greed_score        = greed,
            accumulation_score = accum,
            distribution_score = distrib,
            regime             = regime,
            confidence         = confidence,
            direction_1h       = round(0.5 + (greed - panic) * 0.15, 3),
            direction_4h       = round(0.5 + (greed - panic) * 0.12, 3),
            direction_24h      = round(0.5 + (greed - panic) * 0.08, 3),
            news_shock_score   = round(news_shock, 3),
        )
