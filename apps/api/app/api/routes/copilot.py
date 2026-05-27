from __future__ import annotations

"""
BehaviorTrade Copilot — streaming chat endpoint.

POST /api/copilot/chat
  Body: { message, context }
  Response: text/event-stream  (SSE chunks)

GET  /api/copilot/context
  Returns current live context (behavioral scores, forecast summary, etc.)
  so the frontend can display what was injected into the prompt.
"""

import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.redis_client import get_json

logger = logging.getLogger(__name__)

router = APIRouter()

# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM = """You are BehaviorTrade Copilot, an expert crypto trading assistant embedded inside the BehaviorTrade app.

Your primary goal is to help users understand and *use* what they see on the current screen:
- Market regime (e.g., sideways, bullish, bearish) and behavioral scores
- GNN forecasts and their confidence/accuracy
- Strategy performance (Trend, Swing, Scalping, Range, DCA, HODL, Futures, Arb, DeFi, etc.)
- Overlays such as Panic, Greed, Accumulation, Distribution
- Whale Flow, Social Sentiment, and News feeds

GENERAL PRINCIPLES
- Always be **clear, concrete, and concise**. Assume the user is smart but busy.
- Never give financial, legal, or tax advice. Emphasize that all outputs are **research & analysis only, not financial advice.**
- Explain probabilities, confidence, and risk honestly. Do not exaggerate edge or certainty.
- Use plain language first; only then add technical detail for advanced users.
- Prefer short paragraphs over long walls of text. Avoid unnecessary jargon.

APP CONTEXT AWARENESS
When responding, always anchor explanations to the *current screen state* provided in the [LIVE CONTEXT] block.
- Reference the visible market regime and confidence.
- Reference the visible GNN forecasts and metrics.
- Reference strategy performance over the shown window and regime.
- If a value is low-confidence, explicitly say so and hedge the interpretation.

INTERPRETING KEY MODULES
1. Market Regime & Behavioral Scores
   - Briefly describe what the current regime implies for traders.
   - Explain behavioral scores (Fear, Panic, Greed, Accumulation, Distribution, Confidence, News Shock) in intuitive terms.
   - Always remind users that these are *indicators*, not guarantees.

2. GNN Predictions
   - Clarify what "Bullish / Bearish / Sideways" plus percentage and confidence mean.
   - When confidence is low or moderate, say that explicitly and advise caution.

3. Strategy Performance
   - Explain which strategies have performed relatively better or worse over the visible period.
   - Emphasize *fit to regime*: e.g., "Scalping and Range tend to suit sideways markets."
   - Never tell the user what to trade; phrase as "this tends to be used for…" or "historically this type of strategy may be more suitable when…"

4. Social Sentiment, Whale Flow, and News
   - Summarize sentiment patterns and what they may signal short-term.
   - For whale flow, explain in plain language what the data suggests.

USER EXPERIENCE & TONE
- Default tone: calm, neutral, and non-hype.
- Be especially clear about uncertainty, risk, and drawdowns.
- If the user seems new, give simple definitions of any technical term.
- If the user seems advanced (asks about Sharpe, regime filters, model architecture), provide more technical depth.

GUARDRAILS
- Never say "guaranteed", "certain", "safe profit", or similar language.
- Always end with: "Research & analysis only. Not financial advice."
- If asked for explicit trading instructions, politely decline and instead explain how to interpret the current signals."""


# ── Request / Response models ─────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class CopilotRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)


# ── Live context builder ──────────────────────────────────────────────────────

async def _build_live_context(client_context: dict) -> str:
    """
    Merge client-supplied context with fresh Redis data into a compact string
    that gets injected into the user turn.
    """
    parts: list[str] = []

    # ── Behavioral scores ──────────────────────────────────────────────────────
    scores = await get_json("behavioral_scores_latest") or client_context.get("scores", {})
    if scores:
        regime = scores.get("regime", "unknown")
        conf   = scores.get("confidence", 0)
        parts.append(
            f"Regime: {regime} ({conf:.0f}% confidence)\n"
            f"Behavioral scores — Panic: {scores.get('panic_score', 0):.0f}, "
            f"Greed: {scores.get('greed_score', 0):.0f}, "
            f"Accumulation: {scores.get('accumulation_score', 0):.0f}, "
            f"Distribution: {scores.get('distribution_score', 0):.0f}, "
            f"News Shock: {scores.get('news_shock_score', 0):.0f}"
        )
        dir_1h  = scores.get("direction_1h",  50)
        dir_4h  = scores.get("direction_4h",  50)
        dir_24h = scores.get("direction_24h", 50)
        parts.append(
            f"GNN direction probs — 1h: {dir_1h:.1f}%, 4h: {dir_4h:.1f}%, 24h: {dir_24h:.1f}%"
        )

    # ── Selected asset & price ─────────────────────────────────────────────────
    asset = client_context.get("asset", "BTC")
    coin_map = {
        "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
        "BNB": "binancecoin", "XRP": "ripple",
    }
    price_data = await get_json(f"price:{coin_map.get(asset, 'bitcoin')}") or {}
    if price_data:
        parts.append(
            f"Selected asset: {asset}/USDT — "
            f"Price: ${price_data.get('price', 0):,.2f}, "
            f"24h change: {price_data.get('change_24h', 0):+.2f}%"
        )
    else:
        parts.append(f"Selected asset: {asset}/USDT")

    # ── Fear & Greed ───────────────────────────────────────────────────────────
    fg = await get_json("fear_greed_latest") or {}
    if fg:
        parts.append(
            f"Market Fear & Greed Index: {fg.get('value', '?')} "
            f"({fg.get('value_classification', '?')})"
        )

    # ── Client-side extras (forecast, strategy perf, etc.) ────────────────────
    if client_context.get("forecast"):
        fc = client_context["forecast"]
        parts.append(
            f"GNN forecast for {asset}: direction={fc.get('direction', '?')}, "
            f"prob_24h={fc.get('prob_24h', 0):.1f}%, "
            f"confidence={fc.get('gnn_confidence', 0):.0f}%"
        )

    if client_context.get("strategies"):
        top = sorted(
            client_context["strategies"],
            key=lambda s: s.get("pnl_30d", 0),
            reverse=True,
        )[:5]
        lines = [f"  {s['name']}: {s.get('pnl_30d', 0):+.1f}% 30d" for s in top]
        parts.append("Top strategies by 30d PnL:\n" + "\n".join(lines))

    return "\n\n".join(parts) if parts else "No live context available."


# ── Streaming chat ─────────────────────────────────────────────────────────────

async def _stream_openai(
    messages: list[dict],
    system: str,
) -> AsyncIterator[str]:
    """Yield SSE-formatted chunks from the OpenAI streaming API."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    stream = await client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1024,
        stream=True,
        messages=[{"role": "system", "content": system}, *messages],
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield f"data: {json.dumps({'text': delta})}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/chat")
async def copilot_chat(req: CopilotRequest):
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY not configured. Add it to your .env file.",
        )

    live_ctx = await _build_live_context(req.context)
    system_with_ctx = _SYSTEM  # base system prompt

    # Build message list: history + new user message with injected context
    messages: list[dict] = []
    for m in req.history[-10:]:  # cap at last 10 turns to control token usage
        messages.append({"role": m.role, "content": m.content})

    user_content = f"[LIVE CONTEXT]\n{live_ctx}\n\n[USER MESSAGE]\n{req.message}"
    messages.append({"role": "user", "content": user_content})

    return StreamingResponse(
        _stream_openai(messages, system_with_ctx),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/context")
async def get_copilot_context():
    """Returns the current live context the copilot would see."""
    ctx = await _build_live_context({})
    return {"context": ctx}
