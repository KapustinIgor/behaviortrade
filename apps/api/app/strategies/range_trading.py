from __future__ import annotations

from app.strategies.base import BaseStrategy, PnLAttribution, StrategySignal


class RangeStrategy(BaseStrategy):
    name = "RANGE"
    display_name = "Range Trading"
    description = "Support/resistance detector — bands widen during fear spikes"

    def compute_signal(self, market_data: dict, gnn_output=None) -> StrategySignal:
        routing = self._apply_gnn(gnn_output, "RANGE")
        modifier = routing["modifier"]
        # TODO: Phase 3 — support/resistance detection + band calculation
        return StrategySignal(state="standby", action=routing["action"], modifier=modifier, gnn_influence=abs(modifier - 1.0), reason=f"Phase 3: range engine pending (band factor: {modifier:.2f}x)")

    def get_pnl_attribution(self) -> PnLAttribution:
        return PnLAttribution(total_pnl=0.0, gnn_contribution=0.0, base_contribution=0.0, trades=0, win_rate=0.0)
