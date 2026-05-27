from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BehavioralScore(Base):
    __tablename__ = "behavioral_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset: Mapped[str] = mapped_column(String(20), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    panic_score: Mapped[float] = mapped_column(Float, nullable=False)
    greed_score: Mapped[float] = mapped_column(Float, nullable=False)
    accumulation_score: Mapped[float] = mapped_column(Float, nullable=False)
    distribution_score: Mapped[float] = mapped_column(Float, nullable=False)
    regime: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_behavioral_asset_ts", "asset", "timestamp"),
    )
