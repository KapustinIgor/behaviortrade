# BehaviorTrade

> Next-generation crypto trading intelligence platform. Markets are driven by human psychology — and that psychology is measurable, graphable, and predictive.

## Core thesis

BehaviorTrade combines all 12 major trading strategies with a Graph Neural Network (GNN) Behavioral Prediction Layer to:
- Predict market movements from human behavior and news
- Visualize historical correlations between price and sentiment
- Connect to every available open data source in real time

## Architecture

```
behaviortrade/
├── apps/
│   ├── api/          # FastAPI backend (Python 3.11+)
│   └── web/          # React 18 + TypeScript frontend
├── deploy/           # Docker / Kubernetes configs
└── docker-compose.yml
```

### Backend stack
- **FastAPI** — async REST + WebSocket API
- **PostgreSQL** — time-series price and behavioral data
- **Neo4j** — participant graph (whales, exchanges, DEXes, social accounts)
- **Redis** — live score cache + pub/sub
- **Celery** — scheduled data ingestion and GNN inference tasks
- **PyTorch + PyTorch Geometric** — 3-layer Graph Attention Network
- **HuggingFace FinBERT** — crypto sentiment NLP

### Frontend stack
- **React 18 + TypeScript + Vite**
- **Zustand** — global state
- **React Query** — server state + caching
- **TradingView Lightweight Charts** — price candlesticks
- **Recharts + D3.js** — behavioral overlays and correlation charts

## Quick start

```bash
cp .env.example .env
# Fill in API keys (CryptoPanic and Reddit are free and recommended for Phase 1)

docker compose up -d postgres redis neo4j
docker compose up api web
```

Frontend: http://localhost:3000  
API docs: http://localhost:8000/docs

## The 12 strategy modules

| # | Strategy | GNN modulation |
|---|---|---|
| 1 | HODLing | Alert only on panic > 0.75 |
| 2 | Day trading | Fear/greed adjusts entry size |
| 3 | Swing trading | Behavioral trend confirmation |
| 4 | Scalping | Halted when panic > 0.8 |
| 5 | Range trading | Widens bands during fear |
| 6 | Trend following | Trend strength × behavior score |
| 7 | Arbitrage | Position size scaled by confidence |
| 8 | DCA | Accelerated on fear, paused on euphoria |
| 9 | Futures/derivatives | Leverage cap enforced by GNN risk score |
| 10 | Algo/bot trading | GNN scores injected as input features |
| 11 | News/sentiment | Primary GNN input signal |
| 12 | DeFi/yield farming | Liquidity risk from GNN |

## Phased roadmap

- **Phase 1 (Weeks 1–4):** CoinGecko + Binance WS + CryptoPanic + Reddit + FinBERT + dashboard + DCA + Arbitrage
- **Phase 2 (Weeks 5–10):** GNN graph construction, GAT model, behavioral score pipeline
- **Phase 3 (Weeks 11–16):** All 12 strategies, backtesting engine, strategy marketplace, correlation explorer
- **Phase 4 (Weeks 17–22):** News impact analyzer, historical replay, prediction feed accuracy tracking, all data sources

## Disclaimer

> This platform is for research, analysis, and strategy assistance — not financial advice. All signals are probabilistic and carry risk. Never execute trades automatically without explicit per-trade confirmation.

## Data sources

35+ open and free/freemium sources including CoinGecko, Binance, Glassnode, CryptoQuant, Reddit, Twitter/X, LunarCrush, Santiment, CryptoPanic, FRED, and more. See [apps/api/app/data_sources/](apps/api/app/data_sources/) for the full list.
