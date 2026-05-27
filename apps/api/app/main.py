from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import create_tables
from app.core.redis_client import close_redis, get_redis
import app.models  # noqa: F401 — ensures all ORM models are registered before create_tables()

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.remove(ws)

    async def broadcast(self, data: Any) -> None:
        payload = json.dumps(data)
        dead: list[WebSocket] = []
        for conn in self._connections:
            try:
                await conn.send_text(payload)
            except Exception:
                dead.append(conn)
        for conn in dead:
            self._connections.remove(conn)


manager = ConnectionManager()


async def _periodic_refresh() -> None:
    """Background loop: refresh prices every 30s, news every 5min, fear/greed every 2h."""
    import asyncio
    from app.core.redis_client import set_json, publish
    from app.data_sources.market.coingecko import CoinGeckoClient
    from app.data_sources.news.cryptopanic import CryptoPanicClient
    from app.data_sources.social.fear_greed import get_fear_greed
    from app.nlp.finbert import analyze_batch

    price_tick    = 0
    news_tick     = 0
    fg_tick       = 0
    sample_tick   = 0
    retrain_tick  = 0
    reddit_tick   = 0
    PRICE_INTERVAL   = 30
    NEWS_INTERVAL    = 300
    FG_INTERVAL      = 7200
    SAMPLE_INTERVAL  = 1800
    RETRAIN_INTERVAL = 86400
    REDDIT_INTERVAL  = 600    # batch-fetch Reddit hot posts every 10 min

    while True:
        await asyncio.sleep(30)
        price_tick    += 30
        news_tick     += 30
        fg_tick       += 30
        sample_tick   += 30
        retrain_tick  += 30
        reddit_tick   += 30

        if price_tick >= PRICE_INTERVAL:
            price_tick = 0
            try:
                cg = CoinGeckoClient()
                assets = ["bitcoin", "ethereum", "solana", "binancecoin", "ripple"]
                data = await cg.get_price(assets)
                for coin_id, prices in data.items():
                    normalized = {
                        "asset": coin_id, "price": prices.get("usd", 0),
                        "change_24h": prices.get("usd_24h_change", 0),
                        "volume_24h": prices.get("usd_24h_vol", 0),
                    }
                    await set_json(f"price:{coin_id}", normalized, ttl=90)
                await publish("price_updates", {"prices": data})
                await cg.close()
            except Exception as e:
                logger.warning("Periodic price refresh failed: %s", e)

            # Recompute and broadcast behavioral scores with each price tick
            try:
                gnn = _gnn_inference
                if gnn is None:
                    from app.gnn.inference import GNNInference
                    gnn = GNNInference()
                scores = await gnn.get_behavioral_scores()
                await set_json("behavioral_scores_latest", scores, ttl=120)
                await publish("behavioral_scores", scores)
            except Exception as e:
                logger.warning("Behavioral score broadcast failed: %s", e)

        if news_tick >= NEWS_INTERVAL:
            news_tick = 0
            try:
                cp = CryptoPanicClient()
                items = await cp.get_news()
                headlines = [i.get("headline", "") for i in items]
                if headlines:
                    sentiments = analyze_batch(headlines)
                    for item, sent in zip(items, sentiments):
                        item["sentiment_score"] = round(sent["score"], 4)
                        item["sentiment_label"] = sent["sentiment"]
                await set_json("news_latest", items[:20], ttl=600)
                await publish("news_updates", {"items": items[:10]})
                await cp.close()
            except Exception as e:
                logger.warning("Periodic news refresh failed: %s", e)

        if fg_tick >= FG_INTERVAL:
            fg_tick = 0
            try:
                fg = await get_fear_greed(limit=30)
                await set_json("fear_greed_latest", fg, ttl=FG_INTERVAL + 300)
            except Exception as e:
                logger.warning("Periodic fear/greed refresh failed: %s", e)

        if reddit_tick >= REDDIT_INTERVAL:
            reddit_tick = 0
            try:
                from app.workers.reddit_sentiment import batch_ingest
                await batch_ingest(limit_per_sub=30)
            except Exception as e:
                logger.warning("Reddit batch ingest failed: %s", e)

        if sample_tick >= SAMPLE_INTERVAL:
            sample_tick = 0
            try:
                from app.gnn.trainer import GNNTrainer
                trainer = GNNTrainer(settings.MODEL_PATH)
                await trainer.collect_sample()
            except Exception as e:
                logger.warning("GNN sample collection failed: %s", e)

        if retrain_tick >= RETRAIN_INTERVAL:
            retrain_tick = 0
            try:
                from app.gnn.trainer import GNNTrainer
                from app.gnn.inference import GNNInference
                trainer = GNNTrainer(settings.MODEL_PATH)
                await trainer.full_retrain()
                # Reload model after training
                gnn = GNNInference()
                await gnn.load_model(settings.MODEL_PATH)
                logger.info("GNN model reloaded after nightly retrain")
            except Exception as e:
                logger.warning("GNN nightly retrain failed: %s", e)


_gnn_inference: "GNNInference | None" = None  # type: ignore[name-defined]


async def _seed_startup_data() -> None:
    from app.core.redis_client import set_json
    from app.data_sources.social.fear_greed import get_fear_greed
    from app.data_sources.market.coingecko import CoinGeckoClient

    try:
        fg = await get_fear_greed(limit=30)
        await set_json("fear_greed_latest", fg, ttl=7200)
        logger.info("Seeded fear/greed: %s (%s)", fg.get("value"), fg.get("value_classification"))
    except Exception as e:
        logger.warning("Fear/greed seed failed: %s", e)

    try:
        cg = CoinGeckoClient()
        assets = ["bitcoin", "ethereum", "solana", "binancecoin", "ripple"]
        data = await cg.get_price(assets)
        for coin_id, prices in data.items():
            await set_json(f"price:{coin_id}", {
                "asset": coin_id, "price": prices.get("usd", 0),
                "change_24h": prices.get("usd_24h_change", 0),
                "volume_24h": prices.get("usd_24h_vol", 0),
            }, ttl=90)
        await cg.close()
        logger.info("Seeded prices for %d assets", len(data))
    except Exception as e:
        logger.warning("Price seed failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _gnn_inference
    logger.info("Starting BehaviorTrade API")
    await create_tables()
    r = await get_redis()
    asyncio.create_task(_redis_subscriber(r))
    asyncio.create_task(_seed_startup_data())
    asyncio.create_task(_periodic_refresh())

    # Load GNN checkpoint if available
    from app.gnn.inference import GNNInference
    _gnn_inference = GNNInference()
    await _gnn_inference.load_model(settings.MODEL_PATH)

    # Start Reddit polling loop (public JSON endpoints — no credentials required)
    from app.workers.reddit_sentiment import stream_loop
    asyncio.create_task(stream_loop())
    logger.info("Reddit poll_loop launched (public endpoints)")

    yield
    await close_redis()
    logger.info("BehaviorTrade API shut down")


async def _redis_subscriber(r) -> None:
    pubsub = r.pubsub()
    await pubsub.subscribe("behavioral_scores", "price_updates", "predictions", "social_signals")
    async for message in pubsub.listen():
        if message["type"] == "message":
            try:
                data = json.loads(message["data"])
                data["channel"] = message["channel"]
                await manager.broadcast(data)
            except Exception as e:
                logger.warning("WS broadcast error: %s", e)


app = FastAPI(
    title="BehaviorTrade API",
    version="0.1.0",
    description="Crypto trading intelligence powered by behavioral GNN",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
from app.api.routes import behavioral, copilot, correlations, gnn as gnn_routes, news, predictions, prices, social, strategies  # noqa: E402

app.include_router(prices.router, prefix="/api/prices", tags=["prices"])
app.include_router(behavioral.router, prefix="/api/behavioral", tags=["behavioral"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["predictions"])
app.include_router(strategies.router, prefix="/api/strategies", tags=["strategies"])
app.include_router(news.router, prefix="/api/news", tags=["news"])
app.include_router(social.router, prefix="/api/social", tags=["social"])
app.include_router(correlations.router, prefix="/api/correlations", tags=["correlations"])
app.include_router(gnn_routes.router, prefix="/api/gnn", tags=["gnn"])
app.include_router(copilot.router, prefix="/api/copilot", tags=["copilot"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.websocket("/ws/behavioral")
async def ws_behavioral(websocket: WebSocket):
    """Streams behavioral score updates directly to the frontend."""
    await websocket.accept()
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe("behavioral_scores")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(
                    message["data"] if isinstance(message["data"], str)
                    else message["data"].decode()
                )
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe("behavioral_scores")
