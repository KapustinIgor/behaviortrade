from __future__ import annotations

from app.strategies.base import BaseStrategy, PnLAttribution, StrategySignal


class ScalpingStrategy(BaseStrategy):
    name = "SCALPING"
    display_name = "Scalping"
    description = "Sub-minute bot execution — halted when panic > 0.8"

    def compute_signal(self, market_data: dict, gnn_output=None) -> StrategySignal:
        routing = self._apply_gnn(gnn_output, "SCALPING")
        modifier = routing["modifier"]
        if modifier == 0.0:
            return StrategySignal(state="blocked", action="halt", modifier=0.0, gnn_influence=1.0, reason="Panic > 80% — scalping halted to protect capital")
        # TODO: Phase 3 — sub-minute signal engine
        return StrategySignal(state="standby", action=routing["action"], modifier=modifier, gnn_influence=abs(modifier - 1.0), reason="Phase 3: scalping engine pending")

    def get_pnl_attribution(self) -> PnLAttribution:
        return PnLAttribution(total_pnl=0.0, gnn_contribution=0.0, base_contribution=0.0, trades=0, win_rate=0.0)
