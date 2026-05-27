from __future__ import annotations

import asyncio
import logging

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.data_ingestion.ingest_prices", bind=True, max_retries=3)
def ingest_prices(self):
    asyncio.run(_ingest_prices())


async def _ingest_prices():
    from app.core.redis_client import publish, set_json
    from app.data_sources.market.coingecko import CoinGeckoClient

    cg = CoinGeckoClient()
    try:
        assets = ["bitcoin", "ethereum", "solana", "binancecoin", "ripple"]
        data = await cg.get_price(assets)
        for asset_id, prices in data.items():
            normalized = {
                "asset": asset_id,
                "price": prices.get("usd", 0),
                "change_24h": prices.get("usd_24h_change", 0),
                "volume_24h": prices.get("usd_24h_vol", 0),
            }
            await set_json(f"price:{asset_id}", normalized, ttl=90)
        await publish("price_updates", {"prices": data})
        logger.info("Ingested prices for %d assets", len(data))
    finally:
        await cg.close()


@celery_app.task(name="app.workers.data_ingestion.ingest_news", bind=True, max_retries=3)
def ingest_news(self):
    asyncio.run(_ingest_news())


async def _ingest_news():
    from app.core.redis_client import publish, set_json
    from app.data_sources.news.cryptopanic import CryptoPanicClient
    from app.nlp.finbert import analyze_batch

    cp = CryptoPanicClient()
    try:
        items = await cp.get_news(filter="hot")
        headlines = [i.get("headline", "") for i in items]
        if headlines:
            sentiments = analyze_batch(headlines)
            for item, sent in zip(items, sentiments):
                item["sentiment_score"] = round(sent["score"], 4)
                item["sentiment_label"] = sent["sentiment"]
        await set_json("news_latest", items[:20], ttl=600)
        await publish("news_updates", {"items": items[:10]})
        logger.info("Ingested %d news items", len(items))
    finally:
        await cp.close()


@celery_app.task(name="app.workers.data_ingestion.ingest_fear_greed")
def ingest_fear_greed():
    asyncio.run(_ingest_fear_greed())


async def _ingest_fear_greed():
    from app.core.redis_client import set_json
    from app.data_sources.social.fear_greed import get_fear_greed

    data = await get_fear_greed(limit=30)
    await set_json("fear_greed_latest", data, ttl=7200)
    logger.info("Fear & Greed updated: %s (%s)", data.get("value"), data.get("value_classification"))


@celery_app.task(name="app.workers.data_ingestion.ingest_sentiment")
def ingest_sentiment():
    asyncio.run(_ingest_reddit_sentiment())


async def _ingest_reddit_sentiment():
    from app.workers.reddit_sentiment import batch_ingest
    agg = await batch_ingest(limit_per_sub=30)
    if agg:
        logger.info(
            "Reddit sentiment ingested: %d posts, overall=%.3f",
            agg.get("total_posts", 0), agg.get("overall_sentiment", 0),
        )
