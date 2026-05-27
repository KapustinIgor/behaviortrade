from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GNNOutput:
    panic_score: float        # 0–1
    greed_score: float        # 0–1
    accumulation_score: float # 0–1
    distribution_score: float # 0–1
    regime: str               # bull/bear/sideways/transition
    confidence: float         # 0–1
    direction_1h: float       # P(up) 0–1
    direction_4h: float       # P(up) 0–1
    direction_24h: float      # P(up) 0–1
    news_shock_score: float   # 0–1
