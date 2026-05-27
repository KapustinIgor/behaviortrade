from __future__ import annotations

import logging

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.retrain.nightly_retrain")
def nightly_retrain():
    # TODO: Phase 2 — GNNTrainer().full_retrain(days=90)
    logger.info("Nightly retrain: Phase 2 pending")


@celery_app.task(name="app.workers.retrain.hourly_finetune")
def hourly_finetune():
    # TODO: Phase 2 — GNNTrainer().hourly_finetune()
    logger.info("Hourly fine-tune: Phase 2 pending")


@celery_app.task(name="app.workers.retrain.emergency_retrain")
def emergency_retrain():
    # TODO: Phase 2 — triggered by regime change detector
    logger.info("Emergency retrain: Phase 2 pending")
