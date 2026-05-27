from __future__ import annotations

from app.strategies.base import BaseStrategy, PnLAttribution, StrategySignal


class DeFiYieldStrategy(BaseStrategy):
    name = "DEFI_YIELD"
    display_name = "DeFi / Yield Farming"
    description = "On-chain yield optimizer — LP exposure reduced when distribution > 0.7"

    def compute_signal(self, market_data: dict, gnn_output=None) -> StrategySignal:
        routing = self._apply_gnn(gnn_output, "DEFI_YIELD")
        modifier = routing["modifier"]
        # TODO: Phase 3 — integrate The Graph for live DEX yield data
        return StrategySignal(
            state="standby",
            action=routing["action"],
            modifier=modifier,
            gnn_influence=abs(modifier - 1.0),
            reason="Phase 3: on-chain yield engine pending" if modifier == 1.0 else f"LP exposure adjusted to {modifier:.0%} by distribution signal",
        )

    def get_pnl_attribution(self) -> PnLAttribution:
        return PnLAttribution(total_pnl=0.0, gnn_contribution=0.0, base_contribution=0.0, trades=0, win_rate=0.0)
