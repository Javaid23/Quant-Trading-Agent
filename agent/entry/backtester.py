from __future__ import annotations

from typing import Dict, List

import pandas as pd

from agent.entry.indicators import calculate_macd, calculate_rsi, moving_average_crossover


class Backtester:
    """Simple historical backtest using a small set of indicator rules."""

    def __init__(self, initial_cash: float = 10000.0):
        self.initial_cash = initial_cash

    def run(self, closes: List[float] | pd.Series) -> Dict[str, float | int]:
        series = pd.Series(closes, dtype=float)
        if series.empty:
            return {"total_trades": 0, "win_rate": 0.0, "final_equity": self.initial_cash}

        rsi = calculate_rsi(series)
        macd, signal, _ = calculate_macd(series)
        ma = moving_average_crossover(series, fast=3, slow=5)

        equity = float(self.initial_cash)
        trades = 0
        wins = 0
        open_position = None

        for i in range(1, len(series)):
            current_close = float(series.iloc[i])
            prev_close = float(series.iloc[i - 1])

            bullish = (
                rsi[i] < 70
                and macd[i] > signal[i]
                and ma["fast_ma"][i] > ma["slow_ma"][i]
                and current_close > prev_close
            )
            bearish = (
                rsi[i] > 30
                and macd[i] < signal[i]
                and ma["fast_ma"][i] < ma["slow_ma"][i]
                and current_close < prev_close
            )

            if bullish and open_position is None:
                open_position = {"entry": current_close, "side": "long"}
                trades += 1
            elif bearish and open_position is None:
                open_position = {"entry": current_close, "side": "short"}
                trades += 1
            elif open_position is not None:
                pnl = (current_close - open_position["entry"]) if open_position["side"] == "long" else (open_position["entry"] - current_close)
                equity += pnl
                wins += 1 if pnl > 0 else 0
                open_position = None

        win_rate = (wins / trades) if trades else 0.0
        return {
            "total_trades": int(trades),
            "win_rate": float(win_rate),
            "final_equity": float(equity),
        }
