from __future__ import annotations

import json
from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Walk up from apps/api/app/core/ → project root to find .env
_HERE = Path(__file__).resolve()
_ENV_FILE = next(
    (p / ".env" for p in [_HERE.parent, _HERE.parent.parent, _HERE.parent.parent.parent,
                           _HERE.parent.parent.parent.parent, _HERE.parent.parent.parent.parent.parent]
     if (p / ".env").exists()),
    ".env",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://bt:bt_secret@localhost:5432/behaviortrade"
    REDIS_URL: str = "redis://localhost:6379/0"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "bt_neo4j_secret"

    # ── App ───────────────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me"
    DEBUG: bool = True
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    # ── Market data ───────────────────────────────────────────────────────────
    COINGECKO_API_KEY: str = ""
    BINANCE_API_KEY: str = ""
    BINANCE_SECRET: str = ""
    COINBASE_API_KEY: str = ""
    COINBASE_API_SECRET: str = ""
    KRAKEN_API_KEY: str = ""
    KRAKEN_API_SECRET: str = ""
    COINMARKETCAP_API_KEY: str = ""
    MESSARI_API_KEY: str = ""
    KAIKO_API_KEY: str = ""

    # ── On-chain ──────────────────────────────────────────────────────────────
    GLASSNODE_API_KEY: str = ""
    CRYPTOQUANT_API_KEY: str = ""
    ETHERSCAN_API_KEY: str = ""
    NANSEN_API_KEY: str = ""
    DEBANK_API_KEY: str = ""

    # ── Social ────────────────────────────────────────────────────────────────
    REDDIT_CLIENT_ID: str = ""
    REDDIT_CLIENT_SECRET: str = ""
    REDDIT_USER_AGENT: str = "BehaviorTrade/0.1"
    TWITTER_BEARER_TOKEN: str = ""
    LUNARCRUSH_API_KEY: str = ""
    SANTIMENT_API_KEY: str = ""

    # ── News ──────────────────────────────────────────────────────────────────
    CRYPTOPANIC_API_KEY: str = ""
    NEWSAPI_KEY: str = ""

    # ── Macro ─────────────────────────────────────────────────────────────────
    FRED_API_KEY: str = ""

    # ── GNN / ML ──────────────────────────────────────────────────────────────
    MODEL_PATH: str = "./models/gnn_checkpoint.pt"
    GNN_RETRAIN_HOUR: int = 2

    # ── AI Copilot ────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""


settings = Settings()
