from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SocialSignal(Base):
    __tablename__ = "social_signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    text_embedding: Mapped[list | None] = mapped_column(JSON)
    sentiment: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    influence_weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    asset_mentions: Mapped[list] = mapped_column(JSON, default=list)
    raw_text: Mapped[str | None] = mapped_column(String(5000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_social_platform_ts", "platform", "timestamp"),
    )
