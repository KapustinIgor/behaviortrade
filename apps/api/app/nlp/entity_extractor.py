from __future__ import annotations

KNOWN_ASSETS = {
    "bitcoin", "btc", "ethereum", "eth", "solana", "sol", "bnb", "binance",
    "xrp", "ripple", "cardano", "ada", "avalanche", "avax", "polygon", "matic",
    "chainlink", "link", "uniswap", "uni", "litecoin", "ltc", "dogecoin", "doge",
}

KNOWN_EXCHANGES = {
    "binance", "coinbase", "kraken", "okx", "bybit", "huobi", "kucoin", "gemini",
    "bitfinex", "bitstamp", "ftx",
}


class EntityExtractor:
    def extract_entities(self, text: str) -> list[dict]:
        text_lower = text.lower()
        entities = []

        for asset in KNOWN_ASSETS:
            if asset in text_lower:
                entities.append({"type": "asset", "value": asset.upper()})

        for exchange in KNOWN_EXCHANGES:
            if exchange in text_lower:
                entities.append({"type": "exchange", "value": exchange.title()})

        # TODO: Phase 3 — add NER model for people (Elon Musk, SBF, etc.) and regulatory bodies
        return entities

    def extract_asset_mentions(self, text: str) -> list[str]:
        return [e["value"] for e in self.extract_entities(text) if e["type"] == "asset"]
