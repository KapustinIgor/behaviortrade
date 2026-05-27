from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NewsEvent(Base):
    __tablename__ = "news_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    body_summary: Mapped[str | None] = mapped_column(Text)
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    entities: Mapped[list] = mapped_column(JSON, default=list)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price_impact_1h: Mapped[float | None] = mapped_column(Float)
    price_impact_24h: Mapped[float | None] = mapped_column(Float)
    url: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_news_source_ts", "source", "timestamp"),
        Index("ix_news_sentiment_ts", "sentiment_score", "timestamp"),
    )
