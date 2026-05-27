from __future__ import annotations

import logging

from app.strategies.base import BaseStrategy, PnLAttribution, StrategySignal

logger = logging.getLogger(__name__)

MIN_SPREAD_PCT = 0.003  # 0.3% minimum spread to trade


class ArbitrageStrategy(BaseStrategy):
    name = "ARBITRAGE"
    display_name = "Arbitrage"
    description = "Cross-exchange spread monitor — position size scaled by GNN confidence"

    def __init__(self, gnn_enabled: bool = True) -> None:
        super().__init__(gnn_enabled)
        self._active_spreads: list[dict] = []

    def compute_signal(self, market_data: dict, gnn_output=None) -> StrategySignal:
        routing = self._apply_gnn(gnn_output, "ARBITRAGE")
        modifier = routing["modifier"]
        action = routing["action"]

        spreads = market_data.get("spreads", [])
        viable = [s for s in spreads if s.get("spread_pct", 0) >= MIN_SPREAD_PCT]

        if not viable:
            return StrategySignal(
                state="standby",
                action="no_spread",
                modifier=modifier,
                gnn_influence=abs(modifier - 1.0) if self.gnn_enabled else 0.0,
                reason="No viable spread above minimum threshold",
            )

        state = "active" if modifier > 0.3 else "blocked"
        return StrategySignal(
            state=state,
            action=action,
            modifier=modifier,
            gnn_influence=abs(modifier - 1.0) if self.gnn_enabled else 0.0,
            reason=f"Best spread: {viable[0].get('spread_pct', 0):.2%} on {viable[0].get('symbol')}",
        )

    def find_spread(self, symbol: str, prices: dict[str, float]) -> list[dict]:
        if len(prices) < 2:
            return []
        exchanges = list(prices.keys())
        spreads = []
        for i in range(len(exchanges)):
            for j in range(i + 1, len(exchanges)):
                ex_a, ex_b = exchanges[i], exchanges[j]
                pa, pb = prices[ex_a], prices[ex_b]
                if pa <= 0 or pb <= 0:
                    continue
                spread_pct = abs(pa - pb) / min(pa, pb)
                if spread_pct >= MIN_SPREAD_PCT:
                    buy_exchange = ex_a if pa < pb else ex_b
                    sell_exchange = ex_b if pa < pb else ex_a
                    spreads.append({
                        "symbol": symbol,
                        "buy_exchange": buy_exchange,
                        "sell_exchange": sell_exchange,
                        "buy_price": min(pa, pb),
                        "sell_price": max(pa, pb),
                        "spread_pct": spread_pct,
                    })
        return sorted(spreads, key=lambda x: x["spread_pct"], reverse=True)

    def calculate_position_size(self, spread_pct: float, capital: float, gnn_output=None) -> float:
        routing = self._apply_gnn(gnn_output, "ARBITRAGE")
        base_size = capital * min(spread_pct * 10, 0.1)
        return base_size * routing["modifier"]

    def get_pnl_attribution(self) -> PnLAttribution:
        return PnLAttribution(total_pnl=0.0, gnn_contribution=0.0, base_contribution=0.0, trades=0, win_rate=0.0)
