import datetime as dt
import os
from typing import Dict, Any, List

import pandas as pd
from dotenv import load_dotenv
from alpaca.data.enums import DataFeed
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

    def get_latest_price(self, symbol: str) -> float:
        symbol = (symbol or "").upper().strip()
        if not symbol:
            return 100.0
        try:
            quote = self.get_latest_quote(symbol)
            return float((quote["bid"] + quote["ask"]) / 2.0)
        except Exception:
            try:
                bars = self.get_bars(symbol, limit=30, timeframe="1Day")
                if not bars.empty and "close" in bars.columns:
                    return float(bars["close"].iloc[-1])
            except Exception:
                pass
            return 100.0

    def get_bars(self, symbol: str, limit: int = 100, timeframe: str = "1Day") -> pd.DataFrame:
        tf = self._to_timeframe(timeframe)
        symbol = (symbol or "").upper().strip()
        if not symbol:
            return self._empty_bars_df(limit)

        end_dt = dt.datetime.now(dt.timezone.utc)
        # Calendar days span weekends/holidays, so `limit` trading bars need a wider window. For daily
        # bars we roughly double the lookback and trim to the most recent `limit` rows below, otherwise
        # a request for e.g. 260 daily bars would silently return only ~180 (about 9 months).
        if timeframe == "1Day":
            lookback_days = max(int(limit) * 2, 40)
            request_limit = None
        else:
            lookback_days = max(int(limit), 30)
            request_limit = limit
        start_dt = end_dt - dt.timedelta(days=lookback_days)

        request = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=tf,
            start=start_dt,
            end=end_dt,
            limit=request_limit,
            feed=DataFeed.IEX,
        )
        response = self.client.get_stock_bars(request)

        if hasattr(response, "data") and getattr(response, "data"):
            bar_map = getattr(response, "data")
            if symbol in bar_map:
                bars = bar_map[symbol]
            else:
                bars = []
        elif hasattr(response, "__getitem__"):
            try:
                bars = response[symbol]
            except (KeyError, TypeError):
                bars = []
        else:
            bars = []

        return self._bars_to_df(bars, limit)

    def get_bars_multi(self, symbols: List[str], limit: int = 120, timeframe: str = "1Day") -> Dict[str, pd.DataFrame]:
        """Fetch bars for many symbols in a single API request (used by the fast watchlist scan)."""
        tf = self._to_timeframe(timeframe)
        cleaned = [(s or "").upper().strip() for s in (symbols or []) if s and str(s).strip()]
        if not cleaned:
            return {}

        end_dt = dt.datetime.now(dt.timezone.utc)
        if timeframe == "1Day":
            lookback_days = max(int(limit) * 2, 40)
            request_limit = None
        else:
            lookback_days = max(int(limit), 30)
            request_limit = limit
        start_dt = end_dt - dt.timedelta(days=lookback_days)

        request = StockBarsRequest(
            symbol_or_symbols=cleaned,
            timeframe=tf,
            start=start_dt,
            end=end_dt,
            limit=request_limit,
            feed=DataFeed.IEX,
        )
        response = self.client.get_stock_bars(request)
        bar_map = getattr(response, "data", None) or {}

        result: Dict[str, pd.DataFrame] = {}
        for symbol in cleaned:
            bars = bar_map.get(symbol, []) if isinstance(bar_map, dict) else []
            result[symbol] = self._bars_to_df(bars, limit)
        return result

    @classmethod
    def _bars_to_df(cls, bars, limit: int) -> pd.DataFrame:
        if not bars:
            return cls._empty_bars_df(limit)

        rows = []
        for bar in bars:
            if hasattr(bar, "model_dump"):
                payload = bar.model_dump()
            elif isinstance(bar, dict):
                payload = bar
            else:
                payload = {}

            ts = getattr(bar, "timestamp", payload.get("timestamp", getattr(bar, "t", pd.Timestamp.utcnow())))
            open_val = getattr(bar, "open", payload.get("open", getattr(bar, "o", 0.0)))
            high_val = getattr(bar, "high", payload.get("high", getattr(bar, "h", 0.0)))
            low_val = getattr(bar, "low", payload.get("low", getattr(bar, "l", 0.0)))
            close_val = getattr(bar, "close", payload.get("close", getattr(bar, "c", 0.0)))
            volume_val = getattr(bar, "volume", payload.get("volume", getattr(bar, "v", 0)))

            rows.append({
                "timestamp": ts,
                "open": float(open_val),
                "high": float(high_val),
                "low": float(low_val),
                "close": float(close_val),
                "volume": int(volume_val),
            })
        frame = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
        # Keep only the most recent `limit` bars; the widened window above can return more than requested.
        if limit and len(frame) > int(limit):
            frame = frame.tail(int(limit)).reset_index(drop=True)
        return frame

    @staticmethod
    def _empty_bars_df(limit: int) -> pd.DataFrame:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

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
