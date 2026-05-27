#!/usr/bin/env python3
"""
Train BehaviorGAT from 1 year of historical Binance OHLCV data.

Run from apps/api/:
    python -m scripts.train_historical
    python -m scripts.train_historical --days 365 --epochs 50 --step-hours 4
    python -m scripts.train_historical --days 90  --epochs 30 --step-hours 1

Options:
    --days        Days of history to fetch (default 365, max 365 free on Binance)
    --epochs      Training epochs (default 50)
    --step-hours  Hours between samples — lower = more samples, slower (default 4)
    --model-path  Checkpoint output path (default from .env MODEL_PATH)
    --force       Re-fetch data even if cache exists
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Make sure app/ is importable when run as `python -m scripts.train_historical`
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("train_historical")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--days",       type=int,   default=365, help="Days of history (default 365)")
    p.add_argument("--epochs",     type=int,   default=50,  help="Training epochs (default 50)")
    p.add_argument("--step-hours", type=int,   default=4,   help="Hours between samples (default 4)")
    p.add_argument("--model-path", type=str,   default=None)
    p.add_argument("--force",      action="store_true", help="Delete cache and re-fetch")
    return p.parse_args()


async def main() -> None:
    args = parse_args()

    # Resolve model path
    model_path = args.model_path
    if not model_path:
        # Try to read from .env
        env_file = Path(__file__).parent.parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("MODEL_PATH="):
                    model_path = line.split("=", 1)[1].strip()
                    break
    model_path = model_path or "./models/gnn_checkpoint.pt"

    # Delete cache if --force
    if args.force:
        from app.gnn.historical_data import CACHE_DIR
        cache = CACHE_DIR / f"historical_{args.days}d.json"
        if cache.exists():
            cache.unlink()
            logger.info("Cache deleted: %s", cache)

    logger.info("=" * 60)
    logger.info("BehaviorGAT Historical Trainer")
    logger.info("  days       = %d", args.days)
    logger.info("  epochs     = %d", args.epochs)
    logger.info("  step_hours = %d  (~%d samples)", args.step_hours,
                args.days * 24 // args.step_hours)
    logger.info("  model_path = %s", model_path)
    logger.info("=" * 60)

    from app.gnn.historical_trainer import HistoricalTrainer
    trainer = HistoricalTrainer(model_path)
    await trainer.train(
        days       = args.days,
        epochs     = args.epochs,
        step_hours = args.step_hours,
    )

    logger.info("Done. Checkpoint ready at: %s", model_path)
    logger.info("Restart the API to load the new model.")


if __name__ == "__main__":
    asyncio.run(main())
