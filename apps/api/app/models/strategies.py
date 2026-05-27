from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StrategyState(Base):
    __tablename__ = "strategy_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    asset: Mapped[str] = mapped_column(String(20), nullable=False)
    signal_state: Mapped[str] = mapped_column(String(20), nullable=False)  # active/standby/blocked
    gnn_influence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    position_size_modifier: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    action: Mapped[str] = mapped_column(String(50), nullable=False, default="baseline")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_strategy_type_asset_ts", "strategy_type", "asset", "timestamp"),
    )
