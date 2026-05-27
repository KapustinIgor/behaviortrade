from __future__ import annotations

"""Paper trading stub endpoints.

All trades are simulated — no real orders are sent to any exchange.
The API surface is intentionally minimal; it grows as needed.

⚠️  No auto-trading: every trade must be explicitly created by the user
    (or by a confirmed strategy signal, never automatically).
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.paper_trades import PaperTrade

router = APIRouter()


# ── Request / Response schemas ────────────────────────────────────────────────

class PaperTradeCreate(BaseModel):
    asset:      str = Field(..., example="BTC", description="Asset symbol")
    direction:  str = Field(..., example="long", pattern="^(long|short)$")
    entry_price: float = Field(..., gt=0)
    size_usd:   float = Field(default=1000.0, gt=0, le=100_000)
    strategy:   Optional[str] = None
    signal_id:  Optional[str] = None
    model_mode: str = Field(default="mock", pattern="^(mock|trained)$")
    regime:     Optional[str] = None
    note:       Optional[str] = None


class PaperTradeClose(BaseModel):
    exit_price: float = Field(..., gt=0)


class PaperTradeOut(BaseModel):
    id:          int
    asset:       str
    direction:   str
    entry_price: float
    exit_price:  Optional[float]
    size_usd:    float
    is_open:     bool
    result_pct:  Optional[float]
    model_mode:  str
    regime:      Optional[str]
    strategy:    Optional[str]
    signal_id:   Optional[str]
    opened_at:   datetime
    closed_at:   Optional[datetime]

    class Config:
        from_attributes = True


def _to_out(t: PaperTrade) -> dict:
    return {
        "id":          t.id,
        "asset":       t.asset,
        "direction":   t.direction,
        "entry_price": t.entry_price,
        "exit_price":  t.exit_price,
        "size_usd":    t.size_usd,
        "is_open":     t.is_open,
        "result_pct":  t.result_pct,
        "model_mode":  t.model_mode,
        "regime":      t.regime,
        "strategy":    t.strategy,
        "signal_id":   t.signal_id,
        "opened_at":   t.opened_at.isoformat(),
        "closed_at":   t.closed_at.isoformat() if t.closed_at else None,
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("")
async def list_paper_trades(
    asset:   Optional[str] = Query(default=None),
    is_open: Optional[bool] = Query(default=None),
    limit:   int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List paper trades, optionally filtered by asset and open/closed status."""
    stmt = select(PaperTrade).order_by(PaperTrade.opened_at.desc()).limit(limit)
    if asset:
        stmt = stmt.where(PaperTrade.asset == asset.upper())
    if is_open is not None:
        stmt = stmt.where(PaperTrade.is_open == is_open)
    result = await db.execute(stmt)
    trades = result.scalars().all()
    return {"trades": [_to_out(t) for t in trades], "count": len(trades)}


@router.post("", status_code=201)
async def create_paper_trade(
    body: PaperTradeCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Open a new simulated paper trade.

    ⚠️  Research / simulation only — no real orders are placed.
    Only open trades when you have explicitly reviewed the signal.
    """
    trade = PaperTrade(
        asset       = body.asset.upper(),
        direction   = body.direction,
        entry_price = body.entry_price,
        size_usd    = body.size_usd,
        strategy    = body.strategy,
        signal_id   = body.signal_id,
        model_mode  = body.model_mode,
        regime      = body.regime,
        is_open     = True,
    )
    db.add(trade)
    await db.commit()
    await db.refresh(trade)
    return {
        "message": "Paper trade opened (simulation only — no real order placed)",
        "trade": _to_out(trade),
    }


@router.get("/{trade_id}")
async def get_paper_trade(
    trade_id: int,
    db: AsyncSession = Depends(get_db),
):
    trade = await db.get(PaperTrade, trade_id)
    if not trade:
        raise HTTPException(404, f"Paper trade {trade_id} not found")
    return _to_out(trade)


@router.patch("/{trade_id}/close")
async def close_paper_trade(
    trade_id: int,
    body: PaperTradeClose,
    db: AsyncSession = Depends(get_db),
):
    """Close an open paper trade at the given exit price, computing simulated P&L."""
    trade = await db.get(PaperTrade, trade_id)
    if not trade:
        raise HTTPException(404, f"Paper trade {trade_id} not found")
    if not trade.is_open:
        raise HTTPException(400, "Trade is already closed")

    entry = trade.entry_price
    exit_ = body.exit_price
    if entry > 0:
        if trade.direction == "long":
            result_pct = round((exit_ - entry) / entry * 100, 3)
        else:  # short
            result_pct = round((entry - exit_) / entry * 100, 3)
    else:
        result_pct = 0.0

    trade.exit_price  = exit_
    trade.result_pct  = result_pct
    trade.is_open     = False
    trade.closed_at   = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(trade)
    return {
        "message": "Paper trade closed",
        "trade": _to_out(trade),
        "result_pct": result_pct,
    }


@router.get("/summary/stats")
async def paper_trade_stats(
    asset: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate P&L statistics across all closed paper trades."""
    stmt = select(PaperTrade).where(PaperTrade.is_open == False)  # noqa: E712
    if asset:
        stmt = stmt.where(PaperTrade.asset == asset.upper())
    result = await db.execute(stmt)
    closed = result.scalars().all()

    if not closed:
        return {"total_trades": 0, "win_rate": 0.0, "avg_return_pct": 0.0, "total_pnl_pct": 0.0}

    returns = [t.result_pct for t in closed if t.result_pct is not None]
    wins    = [r for r in returns if r > 0]
    win_rate = round(len(wins) / len(returns) * 100, 1) if returns else 0.0
    avg_ret  = round(sum(returns) / len(returns), 3) if returns else 0.0
    total    = round(sum(returns), 3)

    return {
        "total_trades":    len(closed),
        "win_rate":        win_rate,
        "avg_return_pct":  avg_ret,
        "total_pnl_pct":   total,
    }
