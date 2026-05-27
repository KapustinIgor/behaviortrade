from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class RegimeDetector:
    def detect_regime(self, price_history: list[float], behavioral_scores: dict) -> str:
        if len(price_history) < 2:
            return "sideways"

        panic = behavioral_scores.get("panic_score", 50) / 100.0
        greed = behavioral_scores.get("greed_score", 50) / 100.0

        recent = price_history[-1]
        earlier = price_history[max(0, len(price_history) - 24)]
        price_change = (recent - earlier) / earlier if earlier > 0 else 0.0

        if price_change > 0.05 and greed > 0.6:
            return "bull"
        if price_change < -0.05 and panic > 0.5:
            return "bear"
        if abs(price_change) < 0.02:
            return "sideways"
        return "transition"

    def check_emergency_retrain(self, current_regime: str, previous_regime: str) -> bool:
        # Major regime shifts warrant emergency retrain
        major_shifts = {
            ("bull", "bear"),
            ("bear", "bull"),
            ("sideways", "bear"),
            ("transition", "bear"),
        }
        return (previous_regime, current_regime) in major_shifts
