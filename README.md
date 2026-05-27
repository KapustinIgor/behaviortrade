# BehaviorTrade

> Crypto behavioral intelligence platform — research tool combining 12 trading strategies with a Graph Neural Network behavioral prediction layer.

---

> ⚠️ **NOT FINANCIAL ADVICE.** BehaviorTrade is a research and strategy-simulation platform. All signals are probabilistic, backtested on historical data, and carry real risk. Do NOT execute live trades based solely on these signals. Always apply your own judgment.

---

## What it does

BehaviorTrade combines:
- **12 strategy modules** (HODL, DCA, Swing, Trend Following, Scalping, Range, Day Trading, Algo Bot, News Sentiment, Futures, Arbitrage, DeFi Yield)
- **Behavioral GNN** — a PyTorch Geometric Graph Attention Network trained on price, sentiment, whale flows, and fear/greed data
- **Correlation Explorer** — Pearson correlations between behavioral signals and price changes at multiple lags
- **Strategy 3D Graph** — WebGL force-graph of strategy synergies, regime fit, and behavioral influences
- **AI Copilot** — GPT-4o-mini assistant with live market context
- **Paper Trading** — simulated trade journal (no real orders, ever)
- **Alert Stubs** — price/regime/signal trigger definitions (delivery not yet implemented)

---

## GNN Model Status

**Current mode: MOCK (Phase 1)**

The GNN uses **heuristic scores derived from Fear & Greed + news sentiment** until a trained checkpoint is available. A `model_mode` field in every API response tells you exactly which mode is active:

| `model_mode` | Meaning |
|---|---|
| `"mock"` | Scores are computed from fear/greed and news via simple formulas — not trained inference |
| `"trained"` | A real BehaviorGAT checkpoint is loaded and running |

The UI shows a **MOCK** (yellow) or **TRAINED** (green) badge in the Behavioral Graph and 3D Strategy Graph.

**What this means for you:**
- In mock mode, all GNN-derived signals are **research estimates only**
- Regime detection, confidence scores, and behavioral overlays are heuristic approximations
- Once a checkpoint is trained (`python scripts/train_historical.py`), the system auto-upgrades to trained mode on the next restart

---

## Data Quality

Not all correlation signals are equally reliable:

| Signal | Source | Quality |
|---|---|---|
| Fear & Greed | alternative.me | `real` — direct measurement |
| Whale Inflow | blockchain.info | `real` — on-chain data |
| Reddit/Social Sentiment | Reddit public JSON | `mixed` — scored posts |
| News Sentiment | CryptoPanic | `mixed` — NLP scores |
| Twitter Volume | Proxy from social sentiment | `proxy` — not direct |
| Google Trends | Proxy from fear/greed extremity | `proxy` — not direct |

The Correlation Explorer shows `REAL`, `MIXED`, or `PROXY` badges and includes warnings for proxy signals.

---

## Architecture

```
behaviortrade/
├── apps/
│   ├── api/          # FastAPI backend (Python 3.11+)
│   └── web/          # React 18 + TypeScript frontend
└── docker-compose.yml
```

### Backend stack
- **FastAPI** — async REST + WebSocket API
- **PostgreSQL** — time-series + paper trades + alerts
- **Neo4j** — participant graph (whales, exchanges, DEXes, social accounts)
- **Redis** — live score cache + pub/sub
- **PyTorch + PyTorch Geometric** — 3-layer BehaviorGAT (Graph Attention Network)
- **HuggingFace FinBERT** — crypto sentiment NLP
- **OpenAI gpt-4o-mini** — AI Copilot (SSE streaming)

### Frontend stack
- **React 18 + TypeScript + Vite**
- **TanStack Query** — server state + caching
- **react-force-graph-3d + Three.js** — WebGL 3D strategy graph
- **TradingView Lightweight Charts** — price candlesticks
- **Recharts** — behavioral overlays and correlation charts

---

## Quick start

```bash
cp .env.example .env
# Edit .env — set real values for:
#   POSTGRES_PASSWORD, NEO4J_PASSWORD
#   OPENAI_API_KEY       (required for Copilot)
#   CRYPTOPANIC_API_KEY  (optional, improves news feed)
# NEVER commit .env to git

docker compose up -d postgres redis neo4j
docker compose up api web
```

Frontend: http://localhost:3000  
API docs: http://localhost:8000/docs

---

## Security

- **Secrets** — all passwords and API keys must be in `.env` (not committed). See `.env.example` for required variables.
- **Database ports** — Postgres, Redis, Neo4j all bind to `127.0.0.1` only in `docker-compose.yml`. Never expose them publicly.
- **No exchange keys in repo** — exchange API keys must never be committed. Paper trading uses no exchange connection.
- **No auto-trading** — the platform never places real orders. Paper trading is simulation only. Live trading requires explicit per-trade confirmation (not yet implemented).

---

## The 12 strategy modules

| # | Strategy | Signal method | GNN modulation |
|---|---|---|---|
| 1 | HODL | Buy on day 1, hold forever | Alert on panic > 0.75 |
| 2 | Day Trading | EMA5/EMA20 crossover | Fear/greed adjusts entry size |
| 3 | Swing | RSI(14) mean-reversion | Behavioral trend confirmation |
| 4 | Scalping | Bollinger squeeze | Halted when panic > 0.8 |
| 5 | Range | Bollinger Band mean reversion (wide) | Bands widen during fear |
| 6 | Trend Following | MACD crossover + EMA200 filter | Trend strength × behavior score |
| 7 | Arbitrage | 48h MA deviation ±2% | Position size scaled by confidence |
| 8 | DCA | Buy on weekly dips | Accelerated on fear, paused on euphoria |
| 9 | Futures | Same as Trend Following (3× leverage) | Leverage cap enforced by GNN risk |
| 10 | Algo Bot | RSI + MACD composite | GNN scores injected as features |
| 11 | News Sentiment | Pullback after uptrend | Primary GNN input signal |
| 12 | DeFi Yield | EMA30/EMA90 accumulation | Liquidity risk from GNN |

Backtest includes: fees (0.1% per side), slippage (0.05%), max drawdown, Sharpe approx, profit factor, and buy-and-hold benchmark.

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/strategies/performance/{asset}` | Backtest results for all 12 strategies |
| GET | `/api/gnn/strategy-graph?asset=BTC` | 3D force-graph data |
| GET | `/api/gnn/graph` | Behavioral participant graph |
| GET | `/api/correlations/top?asset=BTC` | Best-lag correlations per signal |
| GET | `/api/predictions` | GNN directional predictions |
| GET | `/api/behavioral/scores` | Live behavioral scores |
| POST | `/api/paper-trades` | Open a paper trade (simulation only) |
| PATCH | `/api/paper-trades/{id}/close` | Close a paper trade |
| GET | `/api/paper-trades/summary/stats` | P&L statistics |
| GET | `/api/alerts` | List alert configurations |
| POST | `/api/alerts` | Create an alert |
| PATCH | `/api/alerts/{id}` | Update an alert |
| DELETE | `/api/alerts/{id}` | Delete an alert |
| POST | `/api/copilot/chat` | AI Copilot (SSE streaming) |

---

## Roadmap

- [x] 12 strategy modules with backtest engine (fees + slippage + drawdown)
- [x] Behavioral GNN (mock scores in Phase 1, trained model in Phase 2)
- [x] Correlation Explorer with data quality labels
- [x] Strategy 3D force-graph (WebGL, react-force-graph-3d)
- [x] AI Copilot (GPT-4o-mini, SSE streaming)
- [x] Paper trading journal (simulation only)
- [x] Alert configuration stubs
- [ ] Live GNN checkpoint training (run `scripts/train_historical.py`)
- [ ] Alert delivery (email / Telegram / Discord / webhook)
- [ ] Exchange integration for live paper trading price feeds
- [ ] Portfolio tracker

---

## Running tests

```bash
cd apps/api
python -m pytest tests/ -v
```

Tests cover: Pearson edge cases, lag alignment, simulate_equity PnL correctness, max drawdown, profit factor, no fake correlation fallbacks, and confidence scale invariance.

---

*BehaviorTrade is an independent research project. Use at your own risk.*
