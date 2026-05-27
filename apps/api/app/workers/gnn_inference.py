from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.gnn_inference.run_gnn_inference")
def run_gnn_inference():
    asyncio.run(_run_inference())


async def _run_inference():
    from app.core.redis_client import publish, set_json
    from app.gnn.inference import GNNInference

    gnn = GNNInference()
    scores = await gnn.get_behavioral_scores()
    scores["updated_at"] = datetime.now(timezone.utc).isoformat()

    await set_json("behavioral_scores_latest", scores, ttl=120)
    await publish("behavioral_scores", scores)
    logger.info("GNN inference published: regime=%s confidence=%.1f", scores.get("regime"), scores.get("confidence", 0))
