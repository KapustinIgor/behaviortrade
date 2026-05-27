from __future__ import annotations

import logging

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.correlation_compute.compute_correlations_for_asset")
def compute_correlations_for_asset(asset: str):
    # TODO: Phase 3 — load behavioral + price time series, compute scipy.stats.pearsonr for each lag
    logger.info("Correlation compute for %s: Phase 3 pending", asset)


@celery_app.task(name="app.workers.correlation_compute.update_correlation_cache")
def update_correlation_cache():
    # TODO: Phase 3 — run compute_correlations_for_asset for all tracked assets
    logger.info("Correlation cache update: Phase 3 pending")
