from __future__ import annotations

from app.strategies.base import BaseStrategy, PnLAttribution, StrategySignal


class DayTradingStrategy(BaseStrategy):
    name = "DAY_TRADING"
    display_name = "Day Trading"
    description = "Intraday signal dashboard — fear/greed adjusts entry size"

    def compute_signal(self, market_data: dict, gnn_output=None) -> StrategySignal:
        routing = self._apply_gnn(gnn_output, "DAY_TRADING")
        modifier = routing["modifier"]
        # TODO: Phase 3 — add intraday RSI/MACD signal logic
        return StrategySignal(state="standby", action=routing["action"], modifier=modifier, gnn_influence=abs(modifier - 1.0), reason="Phase 3: intraday signal engine pending")

    def get_pnl_attribution(self) -> PnLAttribution:
        return PnLAttribution(total_pnl=0.0, gnn_contribution=0.0, base_contribution=0.0, trades=0, win_rate=0.0)
