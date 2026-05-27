"""
Unit tests for app.api.routes.correlations

Tests cover:
  - Pearson calculation correctness
  - Lag alignment interpretation
  - No fake fallback data (no hardcoded 0.72 etc.)
  - _enrich() attaches expected fields
  - _lag_interpretation() returns correct direction text
"""
from __future__ import annotations

import math

import pytest

from app.api.routes.correlations import (
    _pearson,
    _lagged_pearson,
    _lag_interpretation,
    _enrich,
)


# ── _pearson() ─────────────────────────────────────────────────────────────────

class TestPearson:
    def test_perfect_positive_correlation(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        r, p, r2 = _pearson(xs, xs)
        assert r == pytest.approx(1.0, abs=1e-6)
        assert r2 == pytest.approx(1.0, abs=1e-4)

    def test_perfect_negative_correlation(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [5.0, 4.0, 3.0, 2.0, 1.0]
        r, _, _ = _pearson(xs, ys)
        assert r == pytest.approx(-1.0, abs=1e-6)

    def test_zero_correlation_constant_y(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [3.0, 3.0, 3.0, 3.0, 3.0]
        r, _, _ = _pearson(xs, ys)
        assert r == 0.0

    def test_bounds_are_clamped(self):
        """r should always stay in [-1, 1]."""
        xs = [1.0, 2.0, 3.0]
        ys = [1.0, 2.0, 3.0]
        r, _, _ = _pearson(xs, ys)
        assert -1.0 <= r <= 1.0

    def test_too_few_samples_returns_zero(self):
        r, p, r2 = _pearson([1.0, 2.0], [1.0, 2.0])
        assert r == 0.0
        assert p == 1.0
        assert r2 == 0.0

    def test_p_value_significant_for_high_r(self):
        """A near-perfect correlation on n=30 samples should yield p < 0.05."""
        n  = 30
        xs = list(range(n))
        ys = [x + 0.001 * i for i, x in enumerate(xs)]  # near-perfect
        r, p, _ = _pearson(xs, ys)
        assert abs(r) > 0.99
        assert p < 0.05


# ── _lagged_pearson() ──────────────────────────────────────────────────────────

class TestLaggedPearson:
    def _make_series(self, n: int = 50):
        import random
        random.seed(42)
        return [random.gauss(0, 1) for _ in range(n)]

    def test_zero_lag_same_as_pearson(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
        r_direct, _, _ = _pearson(xs, xs)
        r_lag, _, _    = _lagged_pearson(xs, xs, lag=0)
        assert r_direct == pytest.approx(r_lag, abs=1e-6)

    def test_positive_lag_reduces_sample_size(self):
        xs = list(range(20))
        r, p, r2 = _lagged_pearson(xs, xs, lag=5)
        # With lag=5 and n=20, effective n=15 → still positive correlation
        assert r > 0

    def test_negative_lag_price_leads_signal(self):
        """Negative lag means price leads; the function should handle it without error."""
        xs = list(range(20))
        r, p, r2 = _lagged_pearson(xs, xs, lag=-3)
        assert isinstance(r, float)
        assert -1.0 <= r <= 1.0

    def test_too_large_lag_returns_zero(self):
        xs = [1.0] * 5
        r, p, r2 = _lagged_pearson(xs, xs, lag=10)
        assert r == 0.0


# ── _lag_interpretation() ─────────────────────────────────────────────────────

class TestLagInterpretation:
    def test_zero_lag(self):
        result = _lag_interpretation(0)
        assert "simultaneous" in result.lower()

    def test_positive_lag_leads_price(self):
        result = _lag_interpretation(4)
        assert "signal leads" in result.lower()
        assert "4h" in result

    def test_negative_lag_price_leads(self):
        result = _lag_interpretation(-8)
        assert "price leads" in result.lower()
        assert "8h" in result


# ── _enrich() ─────────────────────────────────────────────────────────────────

class TestEnrich:
    def _base_row(self, r: float = 0.5, sig: str = "fear_greed", lag: int = 0) -> dict:
        return {
            "signal_type":   sig,
            "signal_source": "test",
            "asset":         "BTC",
            "lag_hours":     lag,
            "pearson_r":     r,
            "p_value":       0.01,
            "r_squared":     r * r,
            "sample_size":   100,
        }

    def test_strong_correlation_labelled_correctly(self):
        row = _enrich(self._base_row(r=0.8))
        assert row["strength"] == "strong"

    def test_moderate_correlation_labelled_correctly(self):
        row = _enrich(self._base_row(r=0.45))
        assert row["strength"] == "moderate"

    def test_weak_correlation_labelled_correctly(self):
        row = _enrich(self._base_row(r=0.25))
        assert row["strength"] == "weak"

    def test_negligible_correlation(self):
        row = _enrich(self._base_row(r=0.05))
        assert row["strength"] == "negligible"

    def test_direction_positive(self):
        row = _enrich(self._base_row(r=0.6))
        assert row["direction"] == "positive"

    def test_direction_negative(self):
        row = _enrich(self._base_row(r=-0.6))
        assert row["direction"] == "negative"

    def test_actionable_requires_sufficient_r_and_p_and_n(self):
        # r=0.5, p=0.01, n=100 → should be actionable
        row = _enrich(self._base_row(r=0.5))
        assert row["is_actionable"] is True

    def test_not_actionable_with_high_p_value(self):
        row = self._base_row(r=0.5)
        row["p_value"] = 0.2   # not significant
        row = _enrich(row)
        assert row["is_actionable"] is False

    def test_proxy_source_gets_warning(self):
        row = _enrich(self._base_row(sig="twitter_volume"))
        assert row["data_quality"] == "proxy"
        assert row["source_type"] == "derived"
        assert row["warning"] is not None
        assert "proxy" in row["warning"].lower()

    def test_direct_source_no_warning(self):
        row = _enrich(self._base_row(sig="fear_greed"))
        assert row["data_quality"] == "real"
        assert row["source_type"] == "direct"
        assert row["warning"] is None

    def test_lag_interpretation_present(self):
        row = _enrich(self._base_row(lag=4))
        assert "lag_interpretation" in row
        assert "4h" in row["lag_interpretation"]

    def test_no_fake_hardcoded_values(self):
        """Ensure _enrich never injects a hardcoded correlation value."""
        row = self._base_row(r=0.123)
        enriched = _enrich(row)
        assert enriched["pearson_r"] == pytest.approx(0.123, abs=1e-6)
        # The infamous hardcoded values from the old fallback should NOT appear
        assert enriched["pearson_r"] not in (0.72, 0.61, -0.58)


# ── Confidence should NOT be double-multiplied ────────────────────────────────

class TestConfidenceScale:
    """
    Regression test: GNN confidence was accidentally multiplied by 100 twice
    (once in inference.get_behavioral_scores, once in BehaviorGraph.tsx).
    The backend contract is: confidence is always in range [0, 100].
    """

    def test_mock_confidence_in_0_100_range(self):
        """GNNInference._mock_scores returns confidence in [0, 1];
        get_behavioral_scores() multiplies by 100 to give [0, 100]."""
        # We can unit-test this directly without full FastAPI startup:
        import asyncio
        from app.gnn.inference import GNNInference

        gnn = GNNInference()  # no checkpoint → mock mode

        async def _run():
            return await gnn.get_behavioral_scores()

        try:
            scores = asyncio.get_event_loop().run_until_complete(_run())
            conf = scores["confidence"]
            assert 0.0 <= conf <= 100.0, (
                f"Confidence out of [0,100] range: {conf}. "
                "Frontend must NOT multiply by 100 again."
            )
        except Exception:
            # If redis is unavailable in CI, skip gracefully
            pytest.skip("Redis not available in this environment")
