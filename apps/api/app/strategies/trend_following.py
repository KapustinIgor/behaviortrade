from __future__ import annotations

from app.strategies.base import BaseStrategy, PnLAttribution, StrategySignal


class TrendFollowingStrategy(BaseStrategy):
    name = "TREND_FOLLOWING"
    display_name = "Trend Following"
    description = "Moving avg + MACD engine — trend strength scaled by behavior score"

    def compute_signal(self, market_data: dict, gnn_output=None) -> StrategySignal:
        routing = self._apply_gnn(gnn_output, "TREND_FOLLOWING")
        modifier = routing["modifier"]
        # TODO: Phase 3 — MACD + moving average crossover signals
        return StrategySignal(state="standby", action=routing["action"], modifier=modifier, gnn_influence=abs(modifier - 1.0), reason=f"Phase 3: trend engine pending (GNN trend boost: {modifier:.2f}x)")

    def get_pnl_attribution(self) -> PnLAttribution:
        return PnLAttribution(total_pnl=0.0, gnn_contribution=0.0, base_contribution=0.0, trades=0, win_rate=0.0)
