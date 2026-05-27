from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "behaviortrade",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.data_ingestion",
        "app.workers.gnn_inference",
        "app.workers.retrain",
        "app.workers.correlation_compute",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    "ingest-prices-every-60s": {
        "task": "app.workers.data_ingestion.ingest_prices",
        "schedule": 60.0,
    },
    "ingest-news-every-5min": {
        "task": "app.workers.data_ingestion.ingest_news",
        "schedule": 300.0,
    },
    "ingest-fear-greed-every-hour": {
        "task": "app.workers.data_ingestion.ingest_fear_greed",
        "schedule": 3600.0,
    },
    "gnn-inference-every-60s": {
        "task": "app.workers.gnn_inference.run_gnn_inference",
        "schedule": 60.0,
    },
    "nightly-retrain": {
        "task": "app.workers.retrain.nightly_retrain",
        "schedule": crontab(hour=settings.GNN_RETRAIN_HOUR, minute=0),
    },
    "hourly-finetune": {
        "task": "app.workers.retrain.hourly_finetune",
        "schedule": crontab(minute=30),
    },
}
