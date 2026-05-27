from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import websockets

logger = logging.getLogger(__name__)

WS_BASE = "wss://stream.binance.com:9443/stream"


class BinanceStreamManager:
    def __init__(self) -> None:
        self._tasks: list[asyncio.Task] = []
        self._running = False

    async def subscribe_ticker(self, symbols: list[str], callback: Callable[[dict], Any]) -> None:
        streams = [f"{s.lower()}@ticker" for s in symbols]
        self._tasks.append(asyncio.create_task(self._stream(streams, callback)))

    async def subscribe_klines(self, symbol: str, interval: str, callback: Callable[[dict], Any]) -> None:
        streams = [f"{symbol.lower()}@kline_{interval}"]
        self._tasks.append(asyncio.create_task(self._stream(streams, callback)))

    async def subscribe_depth(self, symbol: str, callback: Callable[[dict], Any]) -> None:
        streams = [f"{symbol.lower()}@depth20@100ms"]
        self._tasks.append(asyncio.create_task(self._stream(streams, callback)))

    async def _stream(self, streams: list[str], callback: Callable[[dict], Any]) -> None:
        url = f"{WS_BASE}?streams={'/'.join(streams)}"
        delay = 1.0
        while True:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info("Binance WS connected: %s", streams)
                    delay = 1.0
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                            normalized = self._normalize(msg)
                            if normalized:
                                await asyncio.create_task(callback(normalized)) if asyncio.iscoroutinefunction(callback) else callback(normalized)
                        except Exception as e:
                            logger.warning("Binance message error: %s", e)
            except Exception as e:
                logger.warning("Binance WS disconnected (%s) – reconnecting in %.1fs", e, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)

    @staticmethod
    def _normalize(msg: dict) -> dict | None:
        data = msg.get("data", msg)
        event = data.get("e")
        ts = datetime.fromtimestamp(data.get("E", 0) / 1000, tz=timezone.utc).isoformat()

        if event == "24hrTicker":
            return {
                "type": "ticker",
                "asset": data.get("s", "").replace("USDT", ""),
                "symbol": data.get("s"),
                "price": float(data.get("c", 0)),
                "change_24h": float(data.get("P", 0)),
                "volume": float(data.get("v", 0)),
                "quote_volume": float(data.get("q", 0)),
                "high": float(data.get("h", 0)),
                "low": float(data.get("l", 0)),
                "timestamp": ts,
            }

        if event == "kline":
            k = data.get("k", {})
            return {
                "type": "kline",
                "asset": data.get("s", "").replace("USDT", ""),
                "symbol": data.get("s"),
                "interval": k.get("i"),
                "open": float(k.get("o", 0)),
                "high": float(k.get("h", 0)),
                "low": float(k.get("l", 0)),
                "close": float(k.get("c", 0)),
                "volume": float(k.get("v", 0)),
                "is_closed": k.get("x", False),
                "timestamp": ts,
            }

        return None

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
