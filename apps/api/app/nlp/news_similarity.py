from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

_model: Any = None


def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            _model = SentenceTransformer(EMBEDDING_MODEL)
            logger.info("Sentence transformer loaded: %s", EMBEDDING_MODEL)
        except ImportError:
            raise RuntimeError("sentence-transformers not installed")
    return _model


class NewsImpactAnalyzer:
    def __init__(self, db_session=None) -> None:
        self._db = db_session

    async def find_similar_headlines(self, headline: str, top_k: int = 10) -> list[dict]:
        # TODO: Phase 4 — embed headline, cosine-search against news_events.text_embedding
        # Steps:
        #   1. model = _get_model(); embedding = model.encode(headline)
        #   2. Load stored embeddings from DB (or vector store like pgvector)
        #   3. Compute cosine similarity and return top_k matches
        return []

    async def get_historical_impact(self, similar_news: list[dict]) -> dict:
        # TODO: Phase 4 — aggregate price_impact_1h / price_impact_24h from similar events
        # Returns: {median_1h: float, median_24h: float, sample_size: int, percentiles: dict}
        return {
            "median_1h": 0.0,
            "median_24h": 0.0,
            "sample_size": len(similar_news),
            "direction_bias": "neutral",
        }

    async def embed_headline(self, headline: str) -> list[float]:
        # TODO: Phase 4 — encode and return as list for DB storage
        model = _get_model()
        import asyncio

        embedding = await asyncio.get_event_loop().run_in_executor(
            None, model.encode, headline
        )
        return embedding.tolist()
