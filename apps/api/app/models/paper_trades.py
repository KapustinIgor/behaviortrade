from __future__ import annotations

"""Paper trading position model.

All trades are purely simulated — no real exchange orders are placed.
This table records entry/exit intent and tracks simulated P&L.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Identification
    asset:       Mapped[str] = mapped_column(String(20), nullable=False)   # e.g. "BTC"
    strategy:    Mapped[str | None] = mapped_column(String(50))            # e.g. "TREND_FOLLOWING"
    signal_id:   Mapped[str | None] = mapped_column(String(100))           # opaque ref to triggering signal

    # Trade details
    direction:   Mapped[str] = mapped_column(String(5), nullable=False)    # "long" | "short"
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price:  Mapped[float | None] = mapped_column(Float)
    size_usd:    Mapped[float] = mapped_column(Float, nullable=False, default=1000.0)

    # Status
    is_open:     Mapped[bool] = mapped_column(Boolean, default=True)
    result_pct:  Mapped[float | None] = mapped_column(Float)               # % P&L on close

    # GNN context at time of entry
    model_mode:  Mapped[str] = mapped_column(String(10), default="mock")   # "mock" | "trained"
    regime:      Mapped[str | None] = mapped_column(String(20))

    # Timestamps
    opened_at:   Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    closed_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_paper_trades_asset_open", "asset", "is_open"),
    )
