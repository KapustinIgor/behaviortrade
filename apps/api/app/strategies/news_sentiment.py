from __future__ import annotations

from app.strategies.base import BaseStrategy, PnLAttribution, StrategySignal


class NewsSentimentStrategy(BaseStrategy):
    name = "NEWS_SENTIMENT"
    display_name = "News / Sentiment"
    description = "Real-time event scanner — primary GNN input signal driver"

    def compute_signal(self, market_data: dict, gnn_output=None) -> StrategySignal:
        news_shock = getattr(gnn_output, "news_shock_score", 0.0) if gnn_output else 0.0
        if news_shock > 0.7:
            return StrategySignal(state="active", action="news_shock_detected", modifier=1.0, gnn_influence=news_shock, reason=f"High-impact news detected (shock score: {news_shock:.0%})")
        # TODO: Phase 2 — continuously feed FinBERT sentiment into GNN
        return StrategySignal(state="active", action="monitoring", modifier=1.0, gnn_influence=0.1, reason="Scanning news feeds — feeding sentiment to GNN")

    def get_pnl_attribution(self) -> PnLAttribution:
        return PnLAttribution(total_pnl=0.0, gnn_contribution=0.0, base_contribution=0.0, trades=0, win_rate=0.0)
