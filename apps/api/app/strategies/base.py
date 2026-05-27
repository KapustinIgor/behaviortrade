from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class StrategySignal:
    state: str         # "active" | "standby" | "blocked"
    action: str        # e.g. "baseline", "accelerate", "halt"
    modifier: float    # position size multiplier
    gnn_influence: float  # 0–1, how much GNN affected this decision
    reason: str        # human-readable explanation


@dataclass
class PnLAttribution:
    total_pnl: float
    gnn_contribution: float   # P&L attributable to GNN modulation
    base_contribution: float  # P&L from base strategy logic
    trades: int
    win_rate: float


class BaseStrategy(ABC):
    name: str = "base"
    display_name: str = "Base Strategy"
    description: str = ""

    def __init__(self, gnn_enabled: bool = True) -> None:
        self.gnn_enabled = gnn_enabled
        self._pnl_history: list[float] = []

    @abstractmethod
    def compute_signal(self, market_data: dict, gnn_output=None) -> StrategySignal: ...

    @abstractmethod
    def get_pnl_attribution(self) -> PnLAttribution: ...

    def toggle_gnn(self, enabled: bool) -> None:
        self.gnn_enabled = enabled

    def _apply_gnn(self, gnn_output, strategy_key: str) -> dict:
        if not self.gnn_enabled or gnn_output is None:
            return {"modifier": 1.0, "action": "baseline"}
        from app.gnn.confidence_router import route_signal
        return route_signal(gnn_output, strategy_key)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "gnn_enabled": self.gnn_enabled,
        }
