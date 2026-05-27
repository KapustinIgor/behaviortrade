from __future__ import annotations

"""
GraphBuilder — constructs the HeteroData graph from live Redis data + synthetic fill.

Node counts (fixed — model architecture depends on these):
  whale_wallet    : 20   (top BTC holders; features derived from fear/greed + whale flows)
  exchange        : 10   (CEX nodes; features from CoinGecko price data where available)
  dex_pool        : 5    (Uniswap/Curve/Aave; features synthetic from ETH price)
  retail_cluster  : 5    (grouped retail behavior patterns)
  news_source     : 5    (top news sources aggregated from live feed)
  social_account  : 5    (high-influence accounts; synthetic)
  on_chain_contract: 3   (bridge + token contracts; synthetic)

Feature vector (16-dim per node):
  [0]  norm_value      — price / balance / volume normalised 0–1
  [1]  change_1h       — 0.5 = flat, >0.5 = positive, <0.5 = negative
  [2]  change_24h
  [3]  change_7d
  [4]  sentiment       — 0.5 = neutral, 1 = max positive, 0 = max negative
  [5]  behavioral_state — 0 = neutral … 1 = extreme panic
  [6]  accuracy_score  — historical prediction accuracy 0–1
  [7]  volume_rank     — relative volume 0–1
  [8]  fg_signal       — global fear/greed 0–1 (same for all nodes)
  [9]  is_inflow       — 1 if recent large inflow detected
  [10] is_outflow      — 1 if recent large outflow
  [11] news_shock      — 1 if abnormal news frequency
  [12-15] reserved     — 0.0
"""

import asyncio
import hashlib
import logging
import math
from typing import Any

import torch
from torch_geometric.data import HeteroData

logger = logging.getLogger(__name__)

# ── Exchange metadata ──────────────────────────────────────────────────────────
_EXCHANGES = [
    "Binance", "Coinbase", "Kraken", "OKX", "Bybit",
    "Huobi", "KuCoin", "Gemini", "Bitfinex", "Bitstamp",
]

# CoinGecko IDs for exchanges we actually have price data for
_EXCHANGE_ASSETS = {
    0: "bitcoin",    # Binance   — use BTC as proxy
    1: "ethereum",   # Coinbase  — use ETH
    2: "bitcoin",    # Kraken
    3: "ethereum",   # OKX
    4: "solana",     # Bybit
}

_DEX_NAMES = ["Uniswap-v3", "Curve", "Aave-v3", "Compound", "dYdX"]

_NEWS_SOURCES = ["CoinDesk", "CoinTelegraph", "TheBlock", "Decrypt", "Bitcoin.com"]


def _stable_noise(seed: Any, dim: int = 1) -> list[float]:
    """Deterministic pseudo-noise in [0, 1] based on seed hash."""
    h = hashlib.md5(str(seed).encode()).hexdigest()
    values = []
    for i in range(0, min(dim * 2, len(h)), 2):
        values.append(int(h[i : i + 2], 16) / 255.0)
    while len(values) < dim:
        values.append(values[len(values) % len(values)])
    return values[:dim]


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _change_to_feature(pct: float) -> float:
    """Convert a percentage change (-100..+100) to a 0–1 feature (0.5 = flat)."""
    return _clamp01(0.5 + pct / 100.0)


class GraphBuilder:
    async def build_graph(self) -> HeteroData:
        from app.core.redis_client import get_json

        fg_data    = await get_json("fear_greed_latest") or {}
        news_items = await get_json("news_latest")       or []
        whale_data = await get_json("whale_flows:10")    or []

        # Per-asset price data
        prices: dict[str, dict] = {}
        for coin in ["bitcoin", "ethereum", "solana", "binancecoin", "ripple"]:
            p = await get_json(f"price:{coin}") or {}
            if p:
                prices[coin] = p

        fg_value = fg_data.get("value", 50) / 100.0  # 0–1

        # ── Real data fetches (fire concurrently, fall back on any error) ─────
        defi_tvl: dict[str, float] = {}
        exchange_vols: dict[str, float] = {}
        live_whale_txs: list[dict] = []
        social_sentiment: dict = {}

        async def _fetch_defi() -> None:
            nonlocal defi_tvl
            try:
                from app.data_sources.onchain.defi_llama import fetch_defi_tvl
                defi_tvl = await fetch_defi_tvl()
            except Exception as exc:
                logger.warning("defi_tvl fetch skipped: %s", exc)

        async def _fetch_exchange_vols() -> None:
            nonlocal exchange_vols
            try:
                from app.data_sources.market.exchange_volumes import fetch_exchange_volumes
                exchange_vols = await fetch_exchange_volumes()
            except Exception as exc:
                logger.warning("exchange_volumes fetch skipped: %s", exc)

        async def _fetch_whale_txs() -> None:
            nonlocal live_whale_txs
            try:
                from app.data_sources.onchain.whale_scanner import fetch_whale_transactions
                live_whale_txs = await fetch_whale_transactions()
            except Exception as exc:
                logger.warning("whale_txs fetch skipped: %s", exc)

        async def _fetch_social() -> None:
            nonlocal social_sentiment
            try:
                raw = await get_json("social_sentiment:BTC") or {}
                if isinstance(raw, dict):
                    social_sentiment = raw
            except Exception as exc:
                logger.warning("social_sentiment fetch skipped: %s", exc)

        await asyncio.gather(
            _fetch_defi(),
            _fetch_exchange_vols(),
            _fetch_whale_txs(),
            _fetch_social(),
        )

        # Merge live whale txs with any existing whale_flows from Redis
        if live_whale_txs:
            whale_data = live_whale_txs

        data = HeteroData()

        # ── Node features ─────────────────────────────────────────────────
        data["whale_wallet"].x     = self._build_whale_features(fg_value, whale_data, prices)
        data["exchange"].x         = self._build_exchange_features(fg_value, prices, exchange_vols)
        data["dex_pool"].x         = self._build_dex_features(fg_value, prices, defi_tvl)
        data["retail_cluster"].x   = self._build_retail_features(fg_value)
        data["news_source"].x      = self._build_news_features(fg_value, news_items)
        data["social_account"].x   = self._build_social_features(fg_value, social_sentiment)
        data["on_chain_contract"].x = self._build_contract_features(fg_value)

        # ── Edge indices ──────────────────────────────────────────────────
        n_whale    = data["whale_wallet"].x.shape[0]
        n_exchange = data["exchange"].x.shape[0]
        n_dex      = data["dex_pool"].x.shape[0]
        n_news     = data["news_source"].x.shape[0]
        n_social   = data["social_account"].x.shape[0]
        n_whale_inflow = len(whale_data)

        data["whale_wallet",  "fund_flow",              "exchange"    ].edge_index = \
            self._whale_to_exchange_edges(n_whale, n_exchange, whale_data)

        data["exchange",      "fund_flow",              "whale_wallet"].edge_index = \
            self._exchange_to_whale_edges(n_exchange, n_whale)

        data["exchange",      "trade_volume",           "exchange"    ].edge_index = \
            self._full_bipartite_edges(n_exchange, n_exchange, exclude_self=True)

        data["social_account","social_influence",       "social_account"].edge_index = \
            self._ring_edges(n_social)

        data["news_source",   "news_citation",          "news_source" ].edge_index = \
            self._news_citation_edges(n_news, news_items)

        data["whale_wallet",  "liquidity_provision",    "dex_pool"    ].edge_index = \
            self._whale_to_dex_edges(n_whale, n_dex)

        data["whale_wallet",  "historical_correlation", "whale_wallet"].edge_index = \
            self._historical_corr_edges(n_whale, fg_value)

        data["exchange",      "historical_correlation", "dex_pool"    ].edge_index = \
            self._exchange_to_dex_corr_edges(n_exchange, n_dex)

        return data

    # ── Node feature builders ─────────────────────────────────────────────

    def _base_features(self, fg_value: float, node_idx: int, node_type: str,
                       overrides: dict | None = None) -> list[float]:
        """Build the 16-dim feature vector for a single node."""
        noise = _stable_noise(f"{node_type}:{node_idx}", 12)
        panic = _clamp01(0.6 - fg_value)
        behavioral_state = panic * 0.7 + noise[5] * 0.3

        feats = [
            noise[0],                                 # [0]  norm_value
            _clamp01(0.5 + (fg_value - 0.5) * 0.3 + noise[1] * 0.1),  # [1] change_1h
            _clamp01(0.5 + (fg_value - 0.5) * 0.4 + noise[2] * 0.1),  # [2] change_24h
            _clamp01(0.5 + (fg_value - 0.5) * 0.5 + noise[3] * 0.15), # [3] change_7d
            _clamp01(0.5 + (fg_value - 0.5) * 0.2 + noise[4] * 0.1),  # [4] sentiment
            behavioral_state,                          # [5] behavioral_state
            _clamp01(0.5 + noise[6] * 0.3),           # [6] accuracy_score
            noise[7],                                  # [7] volume_rank
            fg_value,                                  # [8] fg_signal (global)
            0.0,                                       # [9]  is_inflow
            0.0,                                       # [10] is_outflow
            0.0,                                       # [11] news_shock
            0.0, 0.0, 0.0, 0.0,                        # [12-15] reserved
        ]
        if overrides:
            for idx, val in overrides.items():
                feats[idx] = _clamp01(float(val))
        return feats

    # CoinGecko exchange IDs corresponding to _EXCHANGES order
    _COINGECKO_EXCHANGE_IDS = [
        "binance", "gdax", "kraken", "okex", "bybit",
        "huobi", "kucoin", "gemini", "bitfinex", "bitstamp",
    ]

    def _build_exchange_features(
        self,
        fg_value: float,
        prices: dict,
        exchange_vols: dict[str, float] | None = None,
    ) -> torch.Tensor:
        # Compute volume ranks from real data if available
        vol_rank: dict[int, float] = {}
        if exchange_vols:
            vols = [
                exchange_vols.get(self._COINGECKO_EXCHANGE_IDS[i], 0.0)
                for i in range(len(_EXCHANGES))
            ]
            max_vol = max(vols) if max(vols) > 0 else 1.0
            vol_rank = {i: vols[i] / max_vol for i in range(len(_EXCHANGES))}

        rows = []
        for i, name in enumerate(_EXCHANGES):
            coin_id = _EXCHANGE_ASSETS.get(i)
            p = prices.get(coin_id, {}) if coin_id else {}
            change_24h = p.get("change_24h", 0.0)
            price_norm = _clamp01(math.log1p(p.get("price", 50000)) / 12.0) if p else 0.5
            overrides = {
                0: price_norm,
                2: _change_to_feature(change_24h),
                8: fg_value,
                # Real volume rank if available, else linear fallback
                7: vol_rank.get(i, 1.0 - i * 0.08),
            }
            rows.append(self._base_features(fg_value, i, "exchange", overrides))
        return torch.tensor(rows, dtype=torch.float32)

    def _build_whale_features(
        self,
        fg_value: float,
        whale_flows: list,
        prices: dict,
    ) -> torch.Tensor:
        rows = []
        btc_change = prices.get("bitcoin", {}).get("change_24h", 0.0)

        for i in range(20):
            tx = whale_flows[i] if i < len(whale_flows) else None
            if tx is not None:
                btc_norm = _clamp01(tx["btc"] / 500.0)
                is_inflow = 1.0  # live unconfirmed txs signal potential exchange inflow
            else:
                btc_norm = 0.0
                is_inflow = 0.0

            overrides = {
                0: btc_norm,
                2: _change_to_feature(btc_change),
                9:  is_inflow,
                10: 0.0,  # direction unknown from unconfirmed data
            }
            rows.append(self._base_features(fg_value, i, "whale_wallet", overrides))
        return torch.tensor(rows, dtype=torch.float32)

    # Mapping from DEX index to DeFiLlama protocol slug
    _DEX_LLAMA_SLUGS = ["uniswap-v3", "curve-dex", "aave-v3", "compound-v3", "dydx"]

    def _build_dex_features(
        self,
        fg_value: float,
        prices: dict,
        defi_tvl: dict[str, float] | None = None,
    ) -> torch.Tensor:
        eth_change = prices.get("ethereum", {}).get("change_24h", 0.0)

        # Compute TVL-based ranks if real data is available
        tvl_norm: dict[int, float] = {}
        vol_rank: dict[int, float] = {}
        if defi_tvl:
            tvls = [defi_tvl.get(self._DEX_LLAMA_SLUGS[i], 0.0) for i in range(len(_DEX_NAMES))]
            max_tvl = max(tvls) if max(tvls) > 0 else 1.0
            for i, tvl in enumerate(tvls):
                tvl_norm[i] = math.log1p(tvl) / 25.0  # normalised log TVL
                vol_rank[i] = tvl / max_tvl

        rows = []
        for i, name in enumerate(_DEX_NAMES):
            overrides: dict[int, float] = {
                2: _change_to_feature(eth_change),
                7: vol_rank.get(i, 1.0 - i * 0.15),
            }
            if i in tvl_norm:
                overrides[0] = tvl_norm[i]
            rows.append(self._base_features(fg_value, i, "dex_pool", overrides))
        return torch.tensor(rows, dtype=torch.float32)

    def _build_retail_features(self, fg_value: float) -> torch.Tensor:
        rows = []
        for i in range(5):
            rows.append(self._base_features(fg_value, i, "retail_cluster"))
        return torch.tensor(rows, dtype=torch.float32)

    def _build_news_features(self, fg_value: float, news_items: list) -> torch.Tensor:
        # Aggregate per source: mean sentiment_score + item count
        source_stats: dict[str, list[float]] = {}
        for item in news_items:
            src = item.get("source", "Unknown")
            score = item.get("sentiment_score", 0.0)
            source_stats.setdefault(src, []).append(score)

        rows = []
        for i, src_name in enumerate(_NEWS_SOURCES):
            scores = source_stats.get(src_name, [])
            mean_sent = (sum(scores) / len(scores)) if scores else 0.0
            shock = 1.0 if len(scores) > 3 else 0.0
            overrides = {
                4: _clamp01(0.5 + mean_sent * 0.5),
                7: min(1.0, len(scores) / 5.0),
                11: shock,
            }
            rows.append(self._base_features(fg_value, i, "news_source", overrides))
        return torch.tensor(rows, dtype=torch.float32)

    def _build_social_features(
        self,
        fg_value: float,
        social_sentiment: dict | None = None,
    ) -> torch.Tensor:
        # social_sentiment:BTC may carry keys like "score" (float -1..1) or "bullish_percent"
        btc_sent: float | None = None
        if social_sentiment:
            raw = social_sentiment.get("score") or social_sentiment.get("bullish_percent")
            if raw is not None:
                try:
                    raw_f = float(raw)
                    # Normalise: if stored as percent (0-100), map to 0-1 first
                    if raw_f > 1.0:
                        raw_f = raw_f / 100.0
                    btc_sent = _clamp01(0.5 + raw_f * 0.5)
                except (TypeError, ValueError):
                    pass

        rows = []
        for i in range(5):
            overrides: dict[int, float] | None = None
            if btc_sent is not None:
                overrides = {4: btc_sent}
            rows.append(self._base_features(fg_value, i, "social_account", overrides))
        return torch.tensor(rows, dtype=torch.float32)

    def _build_contract_features(self, fg_value: float) -> torch.Tensor:
        rows = []
        for i in range(3):
            rows.append(self._base_features(fg_value, i, "on_chain_contract"))
        return torch.tensor(rows, dtype=torch.float32)

    # ── Edge index builders ───────────────────────────────────────────────

    @staticmethod
    def _t(src: list[int], dst: list[int]) -> torch.Tensor:
        if not src:
            return torch.zeros((2, 0), dtype=torch.long)
        return torch.tensor([src, dst], dtype=torch.long)

    def _whale_to_exchange_edges(self, n_whale: int, n_exchange: int,
                                  whale_flows: list) -> torch.Tensor:
        src, dst = [], []
        # Every whale connects to at least one exchange (by index mod)
        for i in range(n_whale):
            src.append(i)
            dst.append(i % n_exchange)
        # Whales with confirmed inflows get additional exchange edges
        for j, _ in enumerate(whale_flows[:5]):
            src.append(j)
            dst.append((j + 1) % n_exchange)
        return self._t(src, dst)

    def _exchange_to_whale_edges(self, n_exchange: int, n_whale: int) -> torch.Tensor:
        src = list(range(n_exchange))
        dst = [(i + 10) % n_whale for i in range(n_exchange)]
        return self._t(src, dst)

    def _full_bipartite_edges(self, n_src: int, n_dst: int,
                               exclude_self: bool = False) -> torch.Tensor:
        src, dst = [], []
        for i in range(n_src):
            for j in range(n_dst):
                if exclude_self and i == j:
                    continue
                src.append(i)
                dst.append(j)
        return self._t(src, dst)

    def _ring_edges(self, n: int) -> torch.Tensor:
        # Forward ring: 0→1→2→…→(n-1)→0; backward ring: 1→0, 2→1, …, 0→(n-1)
        fwd_src = list(range(n))
        fwd_dst = list(range(1, n)) + [0]
        bwd_src = list(range(1, n)) + [0]
        bwd_dst = list(range(n))
        return self._t(fwd_src + bwd_src, fwd_dst + bwd_dst)

    def _news_citation_edges(self, n_news: int, news_items: list) -> torch.Tensor:
        # Sources that cover the same currencies are "cited" by each other
        src = [0, 1, 2, 3, 4, 1, 2][:n_news * 2]
        dst = [1, 2, 3, 4, 0, 3, 0][:n_news * 2]
        return self._t(src, dst)

    def _whale_to_dex_edges(self, n_whale: int, n_dex: int) -> torch.Tensor:
        src, dst = [], []
        for i in range(0, n_whale, 2):
            src.append(i)
            dst.append(i % n_dex)
        return self._t(src, dst)

    def _historical_corr_edges(self, n_whale: int, fg_value: float) -> torch.Tensor:
        # Pair correlated whales; number of pairs scales with fear (more correlation in fear)
        n_pairs = int(10 + fg_value * 10)
        src, dst = [], []
        noise = _stable_noise("whale_corr", n_pairs * 2)
        for k in range(n_pairs):
            i = int(noise[k * 2] * (n_whale - 1))
            j = int(noise[k * 2 + 1] * (n_whale - 1))
            if i != j:
                src += [i, j]
                dst += [j, i]
        return self._t(src, dst)

    def _exchange_to_dex_corr_edges(self, n_exchange: int, n_dex: int) -> torch.Tensor:
        src = [i for i in range(n_exchange) for _ in range(2)]
        dst = [(i * 2) % n_dex for i in range(n_exchange)] + \
              [(i * 2 + 1) % n_dex for i in range(n_exchange)]
        return self._t(src[:n_exchange * 2], dst[:n_exchange * 2])
