from __future__ import annotations

from app.strategies.base import BaseStrategy, PnLAttribution, StrategySignal


class SwingStrategy(BaseStrategy):
    name = "SWING"
    display_name = "Swing Trading"
    description = "2–14 day momentum scanner — behavioral trend confirmation"

    def compute_signal(self, market_data: dict, gnn_output=None) -> StrategySignal:
        routing = self._apply_gnn(gnn_output, "SWING")
        modifier = routing["modifier"]
        # TODO: Phase 3 — add 2-14 day momentum logic + regime confirmation
        return StrategySignal(state="standby", action=routing["action"], modifier=modifier, gnn_influence=abs(modifier - 1.0), reason="Phase 3: swing momentum engine pending")

    def get_pnl_attribution(self) -> PnLAttribution:
        return PnLAttribution(total_pnl=0.0, gnn_contribution=0.0, base_contribution=0.0, trades=0, win_rate=0.0)
