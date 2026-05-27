from __future__ import annotations

"""Price & signal alert model.

Alerts define threshold-based triggers.  The delivery worker (not yet
implemented) reads triggered=False rows and dispatches via the chosen
channel.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Target
    asset:          Mapped[str] = mapped_column(String(20), nullable=False)   # "BTC"
    alert_type:     Mapped[str] = mapped_column(String(30), nullable=False)
    # alert_type options:
    #   "price_above" | "price_below" | "regime_change"
    #   | "confidence_drop" | "strategy_signal" | "fear_greed_above"
    #   | "fear_greed_below"

    threshold:      Mapped[float | None] = mapped_column(Float)               # numeric trigger
    threshold_text: Mapped[str | None] = mapped_column(String(50))            # e.g. regime name

    # Delivery
    channel:        Mapped[str] = mapped_column(String(20), default="email")
    # channel: "email" | "telegram" | "discord" | "webhook"
    destination:    Mapped[str | None] = mapped_column(String(500))
    # email address, telegram chat_id, discord webhook url, or generic url

    # State
    is_active:      Mapped[bool] = mapped_column(Boolean, default=True)
    triggered:      Mapped[bool] = mapped_column(Boolean, default=False)
    triggered_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Optional note
    note:           Mapped[str | None] = mapped_column(String(500))

    created_at:     Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at:     Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_alerts_asset_active", "asset", "is_active"),
    )
