"""
Unit tests for app.strategies.signal_engine

Tests cover:
  - simulate_equity PnL correctness (the old bug was position=0 before pnl_pct calc)
  - Fee and slippage deduction
  - Max drawdown calculation
  - Profit factor
  - Benchmark buy-and-hold return
  - Sharpe approximation (sign, not exact value)
  - Edge cases: no trades, all holds, single price point
"""
from __future__ import annotations

import math

import pytest

# Import the module under test
from app.strategies.signal_engine import simulate_equity


# ── Helpers ────────────────────────────────────────────────────────────────────

def _flat(n: int, price: float = 100.0) -> list[float]:
    return [price] * n


def _rising(n: int, start: float = 100.0, step: float = 1.0) -> list[float]:
    return [start + i * step for i in range(n)]


def _falling(n: int, start: float = 100.0, step: float = 1.0) -> list[float]:
    return [start - i * step for i in range(n)]


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestPnLCalculation:
    """Core P&L correctness — this covers the old 'position=0 before pnl_pct' bug."""

    def test_profitable_trade_has_positive_result(self):
        """Buy at 100, sell at 110 → positive total_return."""
        prices  = [100.0, 100.0, 110.0, 110.0]
        signals = ["hold", "buy", "sell", "hold"]
        _, stats = simulate_equity(prices, signals, fee_rate=0.0, slippage_rate=0.0)
        assert stats["total_return"] > 0, "Expected positive return on buy-low-sell-high"

    def test_losing_trade_has_negative_result(self):
        """Buy at 100, sell at 90 → negative total_return."""
        prices  = [100.0, 100.0, 90.0, 90.0]
        signals = ["hold", "buy", "sell", "hold"]
        _, stats = simulate_equity(prices, signals, fee_rate=0.0, slippage_rate=0.0)
        assert stats["total_return"] < 0, "Expected negative return on buy-high-sell-low"

    def test_pnl_pct_accuracy_no_costs(self):
        """Buy at 100, sell at 120 → +20% gross (no fees/slippage)."""
        prices  = [100.0, 120.0]
        signals = ["buy", "sell"]
        _, stats = simulate_equity(prices, signals, fee_rate=0.0, slippage_rate=0.0)
        assert abs(stats["total_return"] - 20.0) < 0.01

    def test_fees_reduce_return(self):
        """Same trade with fees should return less than without."""
        prices  = [100.0, 120.0]
        signals = ["buy", "sell"]
        _, no_fee   = simulate_equity(prices, signals, fee_rate=0.0, slippage_rate=0.0)
        _, with_fee = simulate_equity(prices, signals, fee_rate=0.001, slippage_rate=0.001)
        assert with_fee["total_return"] < no_fee["total_return"]

    def test_trades_count_is_accurate(self):
        """Three buy-sell pairs → trades == 3."""
        prices  = [100, 110, 100, 110, 100, 110]
        signals = ["buy", "sell", "buy", "sell", "buy", "sell"]
        _, stats = simulate_equity(prices, signals, fee_rate=0.0, slippage_rate=0.0)
        assert stats["trades"] == 3

    def test_win_rate_all_winners(self):
        """All profitable trades → 100% win rate."""
        prices  = [100.0, 110.0, 100.0, 110.0]
        signals = ["buy", "sell", "buy", "sell"]
        _, stats = simulate_equity(prices, signals, fee_rate=0.0, slippage_rate=0.0)
        assert stats["win_rate"] == 100.0

    def test_win_rate_all_losers(self):
        """All losing trades → 0% win rate."""
        prices  = [110.0, 100.0, 110.0, 100.0]
        signals = ["buy", "sell", "buy", "sell"]
        _, stats = simulate_equity(prices, signals, fee_rate=0.0, slippage_rate=0.0)
        assert stats["win_rate"] == 0.0

    def test_no_trades_returns_zero(self):
        """No signals → equity stays flat, win_rate=0, trades=0."""
        prices  = _flat(50, 100.0)
        signals = ["hold"] * 50
        equity, stats = simulate_equity(prices, signals)
        assert stats["trades"] == 0
        assert stats["win_rate"] == 0.0
        # All equity values should be 0% (started at start value, no change)
        assert all(e == 0.0 for e in equity)

    def test_open_position_closed_at_end(self):
        """A position opened but never explicitly closed should be closed at last price."""
        prices  = [100.0, 110.0]
        signals = ["buy", "hold"]
        _, stats = simulate_equity(prices, signals, fee_rate=0.0, slippage_rate=0.0)
        # 100 → 110 with position open = ~+10%
        assert stats["trades"] == 1
        assert stats["total_return"] > 0


class TestMaxDrawdown:
    def test_no_drawdown_on_rising_prices(self):
        """Rising prices with a buy → very low drawdown (only slippage can cause it)."""
        prices  = _rising(20, 100.0, 1.0)
        signals = ["buy"] + ["hold"] * 19
        _, stats = simulate_equity(prices, signals, fee_rate=0.0, slippage_rate=0.0)
        assert stats["max_drawdown"] >= 0.0

    def test_drawdown_detected_on_drop(self):
        """Buy at 100, price drops to 80, then recovers → drawdown ≈ 20%."""
        prices  = [100.0, 90.0, 80.0, 100.0, 110.0]
        signals = ["buy", "hold", "hold", "hold", "sell"]
        _, stats = simulate_equity(prices, signals, fee_rate=0.0, slippage_rate=0.0)
        # Peak 100 → trough 80 = 20% drawdown from perspective of start capital
        assert stats["max_drawdown"] > 10.0

    def test_max_drawdown_is_non_negative(self):
        """max_drawdown should never be negative."""
        for _ in range(5):
            prices  = _rising(10)
            signals = ["buy"] + ["hold"] * 9
            _, stats = simulate_equity(prices, signals)
            assert stats["max_drawdown"] >= 0.0


class TestBenchmark:
    def test_benchmark_rising(self):
        """Benchmark buy-and-hold should be positive on rising prices."""
        prices  = _rising(10, 100.0, 10.0)  # 100 → 190
        signals = ["hold"] * 10
        _, stats = simulate_equity(prices, signals)
        assert stats["benchmark_buy_hold_return"] == pytest.approx(
            (190 - 100) / 100 * 100, rel=1e-3
        )

    def test_benchmark_flat(self):
        """Flat prices → 0% benchmark."""
        prices  = _flat(10, 100.0)
        signals = ["hold"] * 10
        _, stats = simulate_equity(prices, signals)
        assert stats["benchmark_buy_hold_return"] == pytest.approx(0.0, abs=0.01)


class TestProfitFactor:
    def test_profit_factor_positive_when_winning(self):
        """Net winning strategy → profit_factor ≥ 1."""
        prices  = [100, 120, 100, 120]
        signals = ["buy", "sell", "buy", "sell"]
        _, stats = simulate_equity(prices, signals, fee_rate=0.0, slippage_rate=0.0)
        assert stats["profit_factor"] >= 1.0

    def test_profit_factor_zero_when_all_losses(self):
        """All losing trades → profit_factor == 0."""
        prices  = [120, 100, 120, 100]
        signals = ["buy", "sell", "buy", "sell"]
        _, stats = simulate_equity(prices, signals, fee_rate=0.0, slippage_rate=0.0)
        assert stats["profit_factor"] == 0.0

    def test_profit_factor_never_inf(self):
        """profit_factor should be capped (no division by zero exposed)."""
        prices  = [100.0, 110.0]
        signals = ["buy", "sell"]
        _, stats = simulate_equity(prices, signals, fee_rate=0.0, slippage_rate=0.0)
        assert stats["profit_factor"] < 100.0  # capped at 99.9


class TestSharpe:
    def test_sharpe_is_float(self):
        prices  = _rising(50, 100.0, 0.5)
        signals = ["buy"] + ["hold"] * 49
        _, stats = simulate_equity(prices, signals)
        assert isinstance(stats["sharpe_approx"], float)

    def test_sharpe_single_point(self):
        """Only one price point → no change series → sharpe = 0."""
        prices  = [100.0]
        signals = ["buy"]
        _, stats = simulate_equity(prices, signals)
        assert stats["sharpe_approx"] == 0.0


class TestEdgeCases:
    def test_empty_prices(self):
        equity, stats = simulate_equity([], [])
        assert equity == []
        assert stats["trades"] == 0

    def test_single_price(self):
        equity, stats = simulate_equity([100.0], ["hold"])
        assert len(equity) == 1

    def test_leverage_multiplies_position(self):
        """Leverage=2 should roughly double gains."""
        prices  = [100.0, 110.0]
        signals = ["buy", "sell"]
        _, stats_1x = simulate_equity(prices, signals, leverage=1.0, fee_rate=0.0, slippage_rate=0.0)
        _, stats_2x = simulate_equity(prices, signals, leverage=2.0, fee_rate=0.0, slippage_rate=0.0)
        assert stats_2x["total_return"] > stats_1x["total_return"]
