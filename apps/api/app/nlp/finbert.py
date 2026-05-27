from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

MODEL_NAME = "ProsusAI/finbert"
BATCH_SIZE = 32

_analyzer: Any = None


def _get_analyzer():
    global _analyzer
    if _analyzer is None:
        try:
            from transformers import pipeline  # type: ignore

            _analyzer = pipeline(
                "text-classification",
                model=MODEL_NAME,
                tokenizer=MODEL_NAME,
                top_k=None,
                max_length=512,
                truncation=True,
                device=-1,  # CPU; set to 0 for GPU
            )
            logger.info("FinBERT loaded: %s", MODEL_NAME)
        except ImportError:
            logger.warning("transformers not installed — sentiment analysis disabled (pip install transformers torch)")
            _analyzer = None
    return _analyzer


_NEUTRAL = {"sentiment": "neutral", "score": 0.0, "confidence": 0.0, "positive": 0.0, "negative": 0.0, "neutral": 1.0}


def analyze(text: str) -> dict:
    pipe = _get_analyzer()
    if pipe is None:
        return _NEUTRAL.copy()
    results = pipe(text[:512])[0]
    best = max(results, key=lambda x: x["score"])
    label = best["label"].lower()
    scores = {r["label"].lower(): r["score"] for r in results}
    return {
        "sentiment": label,
        "score": scores.get("positive", 0.0) - scores.get("negative", 0.0),
        "confidence": best["score"],
        "positive": scores.get("positive", 0.0),
        "negative": scores.get("negative", 0.0),
        "neutral": scores.get("neutral", 0.0),
    }


def analyze_batch(texts: list[str]) -> list[dict]:
    pipe = _get_analyzer()
    if pipe is None:
        return [_NEUTRAL.copy() for _ in texts]
    truncated = [t[:512] for t in texts]
    all_results = pipe(truncated, batch_size=BATCH_SIZE)
    output = []
    for results in all_results:
        best = max(results, key=lambda x: x["score"])
        label = best["label"].lower()
        scores = {r["label"].lower(): r["score"] for r in results}
        output.append({
            "sentiment": label,
            "score": scores.get("positive", 0.0) - scores.get("negative", 0.0),
            "confidence": best["score"],
            "positive": scores.get("positive", 0.0),
            "negative": scores.get("negative", 0.0),
            "neutral": scores.get("neutral", 0.0),
        })
    return output
