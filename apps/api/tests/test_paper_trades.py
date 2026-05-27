"""Test that /summary/stats route is not shadowed by /{trade_id} route."""
import pytest


def test_stats_route_not_shadowed_by_trade_id():
    """
    FastAPI must resolve /summary/stats before /{trade_id}.
    Check route order in the router.
    """
    from app.api.routes.paper_trades import router
    routes = [r.path for r in router.routes]
    # /summary/stats must appear before /{trade_id}
    summary_idx  = next((i for i, p in enumerate(routes) if p == "/summary/stats"), None)
    trade_id_idx = next((i for i, p in enumerate(routes) if p == "/{trade_id}"), None)
    assert summary_idx is not None, "/summary/stats route not found"
    assert trade_id_idx is not None, "/{trade_id} route not found"
    assert summary_idx < trade_id_idx, (
        f"/summary/stats (index {summary_idx}) must appear before "
        f"/{{trade_id}} (index {trade_id_idx}) to avoid route shadowing"
    )
