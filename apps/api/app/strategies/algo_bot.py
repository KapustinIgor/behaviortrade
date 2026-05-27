from __future__ import annotations

from app.strategies.base import BaseStrategy, PnLAttribution, StrategySignal


class AlgoBotStrategy(BaseStrategy):
    name = "ALGO_BOT"
    display_name = "Algo / Bot Trading"
    description = "Strategy automation layer — GNN behavioral scores injected as input features"

    def compute_signal(self, market_data: dict, gnn_output=None) -> StrategySignal:
        routing = self._apply_gnn(gnn_output, "ALGO_BOT")
        # TODO: Phase 3 — custom algorithm that takes GNN features as direct input
        return StrategySignal(state="standby", action="inject_gnn_features", modifier=1.0, gnn_influence=1.0, reason="Phase 3: bot engine uses GNN scores as direct input features")

    def get_pnl_attribution(self) -> PnLAttribution:
        return PnLAttribution(total_pnl=0.0, gnn_contribution=0.0, base_contribution=0.0, trades=0, win_rate=0.0)
