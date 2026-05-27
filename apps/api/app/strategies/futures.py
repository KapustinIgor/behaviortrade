from __future__ import annotations

from app.strategies.base import BaseStrategy, PnLAttribution, StrategySignal


class FuturesStrategy(BaseStrategy):
    name = "FUTURES"
    display_name = "Futures / Derivatives"
    description = "Leveraged directional bets — leverage cap enforced by GNN risk score"

    def compute_signal(self, market_data: dict, gnn_output=None) -> StrategySignal:
        routing = self._apply_gnn(gnn_output, "FUTURES")
        modifier = routing["modifier"]
        max_leverage = modifier * 10
        # TODO: Phase 3 — directional futures signal logic
        return StrategySignal(
            state="standby",
            action=routing["action"],
            modifier=modifier,
            gnn_influence=1.0 - modifier if modifier < 1.0 else 0.0,
            reason=f"Max leverage capped at {max_leverage:.1f}x by GNN risk score",
        )

    def get_pnl_attribution(self) -> PnLAttribution:
        return PnLAttribution(total_pnl=0.0, gnn_contribution=0.0, base_contribution=0.0, trades=0, win_rate=0.0)
