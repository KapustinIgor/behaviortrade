from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.strategies.base import BaseStrategy, PnLAttribution, StrategySignal


class DCAStrategy(BaseStrategy):
    name = "DCA"
    display_name = "Dollar Cost Averaging"
    description = "Scheduled accumulation — accelerated on fear, paused during euphoria"

    def __init__(self, base_amount: float = 100.0, interval_hours: int = 24, gnn_enabled: bool = True) -> None:
        super().__init__(gnn_enabled)
        self.base_amount = base_amount
        self.interval_hours = interval_hours
        self._next_buy: datetime = datetime.now(timezone.utc)
        self._executed_buys: list[dict] = []

    def compute_signal(self, market_data: dict, gnn_output=None) -> StrategySignal:
        routing = self._apply_gnn(gnn_output, "DCA")
        modifier = routing["modifier"]
        action = routing["action"]

        now = datetime.now(timezone.utc)
        if now < self._next_buy:
            return StrategySignal(
                state="standby",
                action="waiting",
                modifier=modifier,
                gnn_influence=abs(modifier - 1.0),
                reason=f"Next buy in {(self._next_buy - now).seconds // 60}min",
            )

        state = "active"
        if modifier == 0.0:
            state = "blocked"
        elif modifier < 0.7:
            state = "standby"

        return StrategySignal(
            state=state,
            action=action,
            modifier=modifier,
            gnn_influence=abs(modifier - 1.0) if self.gnn_enabled else 0.0,
            reason=self._reason(action),
        )

    def calculate_next_buy(self, gnn_output=None) -> float:
        routing = self._apply_gnn(gnn_output, "DCA")
        amount = self.base_amount * routing["modifier"]
        self._next_buy = datetime.now(timezone.utc) + timedelta(hours=self.interval_hours)
        return amount

    def get_schedule(self) -> list[dict]:
        schedule = []
        t = datetime.now(timezone.utc)
        for i in range(7):
            schedule.append({
                "datetime": t.isoformat(),
                "base_amount": self.base_amount,
                "index": i,
            })
            t += timedelta(hours=self.interval_hours)
        return schedule

    def get_pnl_attribution(self) -> PnLAttribution:
        return PnLAttribution(total_pnl=0.0, gnn_contribution=0.0, base_contribution=0.0, trades=len(self._executed_buys), win_rate=0.0)

    @staticmethod
    def _reason(action: str) -> str:
        return {
            "accelerate": "Fear detected — buying more aggressively",
            "reduce": "Euphoria detected — reducing buy size",
            "increase": "Smart money accumulating — increasing position",
            "baseline": "Normal DCA schedule",
        }.get(action, action)
