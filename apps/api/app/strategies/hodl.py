from __future__ import annotations

from app.strategies.base import BaseStrategy, PnLAttribution, StrategySignal


class HODLStrategy(BaseStrategy):
    name = "HODL"
    display_name = "HODLing"
    description = "Passive hold tracker — GNN triggers alerts only, no size modulation"

    def compute_signal(self, market_data: dict, gnn_output=None) -> StrategySignal:
        panic = (gnn_output.panic_score if gnn_output else 0.0)
        if panic > 0.75:
            return StrategySignal(state="active", action="alert_panic", modifier=1.0, gnn_influence=panic, reason=f"Extreme panic detected ({panic:.0%}) — consider your conviction")
        return StrategySignal(state="active", action="hold", modifier=1.0, gnn_influence=0.0, reason="Holding position")

    def get_pnl_attribution(self) -> PnLAttribution:
        return PnLAttribution(total_pnl=0.0, gnn_contribution=0.0, base_contribution=0.0, trades=0, win_rate=0.0)
