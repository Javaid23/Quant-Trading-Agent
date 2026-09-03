from __future__ import annotations

from typing import Dict, List

import pandas as pd

from agent.entry.indicators import calculate_bollinger_bands, calculate_macd, calculate_rsi, moving_average_crossover


class SignalEngine:
    """Generate a bullish/bearish/neutral signal based on common technical indicators."""

    def __init__(self):
        self.rsi_period = 14
        self.bollinger_period = 20
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9

        # Indicator weights. Our combination backtest (see demo/backtest_results.md) showed momentum
        # (MACD) dragged returns while mean-reversion (Bollinger, RSI) led, so MACD is down-weighted and
        # Bollinger boosted. We keep all four indicators for robustness rather than fitting one regime.
        self.rsi_weight = 20.0
        self.macd_weight = 10.0
        self.bollinger_weight = 20.0
        self.ma_weight = 15.0

    def generate_signal(self, data: pd.DataFrame) -> Dict[str, float | str]:
        if data is None:
            return {"signal": "no_data", "score": 0.0, "reason": "No market data available for this symbol."}

        if not isinstance(data, pd.DataFrame):
            try:
                data = pd.DataFrame(data)
            except Exception:
                return {"signal": "no_data", "score": 0.0, "reason": "No market data available for this symbol."}

        if data.empty or "close" not in data.columns:
            return {"signal": "no_data", "score": 0.0, "reason": "No market data available for this symbol."}

        closes = pd.to_numeric(data["close"], errors="coerce").dropna()
        if closes.empty:
            return {"signal": "no_data", "score": 0.0, "reason": "No market data available for this symbol; no valid close values were returned."}

        if len(closes) < 5:
            return {"signal": "no_data", "score": 0.0, "reason": "No market data available for this symbol; too few valid bars to compute a signal."}

        if closes.nunique() <= 1:
            return {"signal": "no_data", "score": 0.0, "reason": "No market data available for this symbol; close series is flat and not usable for signal generation."}

        rsi = calculate_rsi(closes, self.rsi_period)
        macd, signal_line, _ = calculate_macd(closes, self.macd_fast, self.macd_slow, self.macd_signal)
        bands = calculate_bollinger_bands(closes, self.bollinger_period)
        ma = moving_average_crossover(closes, fast=3, slow=5)

        last_idx = len(closes) - 1

        score = 0.0
        if rsi[last_idx] < 30:
            score += self.rsi_weight
        elif rsi[last_idx] > 70:
            score -= self.rsi_weight

        if macd[last_idx] > signal_line[last_idx]:
            score += self.macd_weight
        else:
            score -= self.macd_weight

        if closes.iloc[last_idx] > bands["middle"][last_idx]:
            score += self.bollinger_weight
        else:
            score -= self.bollinger_weight

        if ma["fast_ma"][last_idx] > ma["slow_ma"][last_idx]:
            score += self.ma_weight
        else:
            score -= self.ma_weight

        if score > 15:
            signal = "bullish"
        elif score < -15:
            signal = "bearish"
        else:
            signal = "neutral"

        return {
            "signal": signal,
            "score": round(float(score), 2),
            "reason": "Composite indicator score based on RSI, MACD, Bollinger, and moving-average trend",
        }
