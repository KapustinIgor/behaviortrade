from app.strategies.algo_bot import AlgoBotStrategy
from app.strategies.arbitrage import ArbitrageStrategy
from app.strategies.base import BaseStrategy, PnLAttribution, StrategySignal
from app.strategies.day_trading import DayTradingStrategy
from app.strategies.dca import DCAStrategy
from app.strategies.defi_yield import DeFiYieldStrategy
from app.strategies.futures import FuturesStrategy
from app.strategies.hodl import HODLStrategy
from app.strategies.news_sentiment import NewsSentimentStrategy
from app.strategies.range_trading import RangeStrategy
from app.strategies.scalping import ScalpingStrategy
from app.strategies.swing import SwingStrategy
from app.strategies.trend_following import TrendFollowingStrategy

STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    "HODL": HODLStrategy,
    "DAY_TRADING": DayTradingStrategy,
    "SWING": SwingStrategy,
    "SCALPING": ScalpingStrategy,
    "RANGE": RangeStrategy,
    "TREND_FOLLOWING": TrendFollowingStrategy,
    "ARBITRAGE": ArbitrageStrategy,
    "DCA": DCAStrategy,
    "FUTURES": FuturesStrategy,
    "ALGO_BOT": AlgoBotStrategy,
    "NEWS_SENTIMENT": NewsSentimentStrategy,
    "DEFI_YIELD": DeFiYieldStrategy,
}

__all__ = [
    "BaseStrategy", "StrategySignal", "PnLAttribution",
    "HODLStrategy", "DayTradingStrategy", "SwingStrategy", "ScalpingStrategy",
    "RangeStrategy", "TrendFollowingStrategy", "ArbitrageStrategy", "DCAStrategy",
    "FuturesStrategy", "AlgoBotStrategy", "NewsSentimentStrategy", "DeFiYieldStrategy",
    "STRATEGY_REGISTRY",
]
