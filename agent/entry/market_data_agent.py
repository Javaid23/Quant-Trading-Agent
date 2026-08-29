import os
from typing import Dict, Any, List

import pandas as pd
from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame


load_dotenv()


class MarketDataAgent:
    """Thin wrapper around Alpaca market data APIs."""

    def __init__(self, api_key: str | None = None, secret_key: str | None = None):
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")

        if not self.api_key or not self.secret_key:
            raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set.")

        self.client = StockHistoricalDataClient(self.api_key, self.secret_key)

    def get_latest_quote(self, symbol: str) -> Dict[str, Any]:
        request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
        response = self.client.get_stock_latest_quote(request)
        quote = response[symbol]
        return {
            "symbol": symbol,
            "ask": float(quote.ask_price),
            "bid": float(quote.bid_price),
            "ask_size": int(quote.ask_size),
            "bid_size": int(quote.bid_size),
        }

    def get_bars(self, symbol: str, limit: int = 100, timeframe: str = "1Day") -> pd.DataFrame:
        tf = self._to_timeframe(timeframe)
        request = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=tf,
            limit=limit,
        )
        response = self.client.get_stock_bars(request)
        bars = response[symbol]
        rows = []
        for bar in bars:
            rows.append({
                "timestamp": bar.t,
                "open": float(bar.o),
                "high": float(bar.h),
                "low": float(bar.l),
                "close": float(bar.c),
                "volume": int(bar.v),
            })
        return pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)

    @staticmethod
    def _to_timeframe(timeframe: str):
        mapping = {
            "1Min": TimeFrame.Minute,
            "5Min": TimeFrame(5, TimeFrame.Minute),
            "1Hour": TimeFrame.Hour,
            "1Day": TimeFrame.Day,
        }
        if timeframe not in mapping:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        return mapping[timeframe]


if __name__ == "__main__":
    agent = MarketDataAgent()
    print(agent.get_latest_quote("AAPL"))
    print(agent.get_bars("AAPL", limit=10, timeframe="1Day").tail())
