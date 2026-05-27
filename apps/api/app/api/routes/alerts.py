from __future__ import annotations

"""Alert management endpoints.

Alerts define threshold-based triggers for price, regime, and signal events.
Delivery (email / Telegram / Discord / webhook) is a planned future feature —
these endpoints manage the alert configuration only.

Alert types:
  price_above       — trigger when asset price exceeds threshold
  price_below       — trigger when asset price drops below threshold
  regime_change     — trigger when GNN regime changes
  confidence_drop   — trigger when GNN confidence falls below threshold
  strategy_signal   — trigger on a specific strategy buy/sell signal
  fear_greed_above  — trigger when Fear & Greed index exceeds threshold
  fear_greed_below  — trigger when Fear & Greed index drops below threshold

Channels (planned): email | telegram | discord | webhook
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.alerts import Alert

router = APIRouter()

_VALID_ALERT_TYPES = {
    "price_above", "price_below", "regime_change",
    "confidence_drop", "strategy_signal",
    "fear_greed_above", "fear_greed_below",
}

_VALID_CHANNELS = {"email", "telegram", "discord", "webhook"}


# ── Request / Response schemas ────────────────────────────────────────────────

class AlertCreate(BaseModel):
    asset:          str = Field(..., example="BTC")
    alert_type:     str = Field(..., description=", ".join(sorted(_VALID_ALERT_TYPES)))
    threshold:      Optional[float] = None
    threshold_text: Optional[str]   = None   # for non-numeric triggers (regime name)
    channel:        str = Field(default="email")
    destination:    Optional[str]   = None   # email/chat_id/webhook URL
    note:           Optional[str]   = None


class AlertUpdate(BaseModel):
    is_active:      Optional[bool]  = None
    threshold:      Optional[float] = None
    threshold_text: Optional[str]   = None
    channel:        Optional[str]   = None
    destination:    Optional[str]   = None
    note:           Optional[str]   = None


def _validate_alert_type(alert_type: str) -> None:
    if alert_type not in _VALID_ALERT_TYPES:
        raise HTTPException(
            400,
            f"Unknown alert_type '{alert_type}'. Valid: {sorted(_VALID_ALERT_TYPES)}",
        )


def _validate_channel(channel: str) -> None:
    if channel not in _VALID_CHANNELS:
        raise HTTPException(
            400,
            f"Unknown channel '{channel}'. Valid: {sorted(_VALID_CHANNELS)}",
        )


def _to_out(a: Alert) -> dict:
    return {
        "id":             a.id,
        "asset":          a.asset,
        "alert_type":     a.alert_type,
        "threshold":      a.threshold,
        "threshold_text": a.threshold_text,
        "channel":        a.channel,
        "destination":    a.destination,
        "is_active":      a.is_active,
        "triggered":      a.triggered,
        "triggered_at":   a.triggered_at.isoformat() if a.triggered_at else None,
        "note":           a.note,
        "created_at":     a.created_at.isoformat(),
        "updated_at":     a.updated_at.isoformat() if a.updated_at else None,
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("")
async def list_alerts(
    asset:     Optional[str]  = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    limit:     int            = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List all configured alerts."""
    stmt = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
    if asset:
        stmt = stmt.where(Alert.asset == asset.upper())
    if is_active is not None:
        stmt = stmt.where(Alert.is_active == is_active)
    result = await db.execute(stmt)
    alerts = result.scalars().all()
    return {"alerts": [_to_out(a) for a in alerts], "count": len(alerts)}


@router.post("", status_code=201)
async def create_alert(
    body: AlertCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new alert.  Delivery is not yet implemented — this stores config only."""
    _validate_alert_type(body.alert_type)
    _validate_channel(body.channel)

    alert = Alert(
        asset          = body.asset.upper(),
        alert_type     = body.alert_type,
        threshold      = body.threshold,
        threshold_text = body.threshold_text,
        channel        = body.channel,
        destination    = body.destination,
        note           = body.note,
        is_active      = True,
        triggered      = False,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return {
        "message": "Alert created. Delivery is planned but not yet implemented.",
        "alert": _to_out(alert),
    }


@router.get("/{alert_id}")
async def get_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
):
    alert = await db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, f"Alert {alert_id} not found")
    return _to_out(alert)


@router.patch("/{alert_id}")
async def update_alert(
    alert_id: int,
    body: AlertUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update alert configuration (activate/deactivate, change threshold, etc.)."""
    alert = await db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, f"Alert {alert_id} not found")

    if body.is_active is not None:
        alert.is_active = body.is_active
    if body.threshold is not None:
        alert.threshold = body.threshold
    if body.threshold_text is not None:
        alert.threshold_text = body.threshold_text
    if body.channel is not None:
        _validate_channel(body.channel)
        alert.channel = body.channel
    if body.destination is not None:
        alert.destination = body.destination
    if body.note is not None:
        alert.note = body.note

    await db.commit()
    await db.refresh(alert)
    return {"message": "Alert updated", "alert": _to_out(alert)}


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete an alert."""
    alert = await db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, f"Alert {alert_id} not found")
    await db.delete(alert)
    await db.commit()
