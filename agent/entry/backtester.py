from __future__ import annotations

from typing import Dict, List

import pandas as pd

from agent.entry.signal_engine import SignalEngine


class Backtester:
    """Historical backtest driven by the live SignalEngine.

    The engine here is the exact same one used for live trading decisions, so the results describe the
    strategy that actually trades (rather than a separate, hand-written set of rules). At each bar we feed
    the engine the closes seen so far, take its bullish/bearish/neutral call, and hold a directional
    position (long on bullish, short on bearish, flat on neutral), flipping or closing when the call
    changes. This mirrors how the agent expresses a view as a long call / long put on each signal.
    """

    def __init__(self, initial_cash: float = 10000.0):
        self.initial_cash = initial_cash
        self.signal_engine = SignalEngine()

    def run(self, closes: List[float] | pd.Series) -> Dict[str, float | int]:
        series = pd.Series(closes, dtype=float).reset_index(drop=True)
        n = len(series)
        if n == 0:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "final_equity": self.initial_cash,
                "total_return_pct": 0.0,
                "strategy": "signal_engine",
            }

        frame = pd.DataFrame({"close": series})

        equity = float(self.initial_cash)
        trades = 0
        wins = 0
        position = 0  # +1 long, -1 short, 0 flat
        entry_price = 0.0

        # The engine needs at least 5 bars to emit a directional signal, so the earliest actionable slice
        # ends at index 4. Iterating slice-by-slice reproduces the information the live agent would have had.
        for i in range(4, n):
            price = float(series.iloc[i])
            signal = self.signal_engine.generate_signal(frame.iloc[: i + 1])["signal"]
            desired = 1 if signal == "bullish" else -1 if signal == "bearish" else 0

            # Close (or flip out of) the current position when the view changes.
            if position != 0 and desired != position:
                pnl = (price - entry_price) * position
                equity += pnl
                trades += 1
                wins += 1 if pnl > 0 else 0
                position = 0

            # Open a new position in the signalled direction.
            if position == 0 and desired != 0:
                position = desired
                entry_price = price

        # Mark any still-open position to the final close so equity reflects it.
        if position != 0 and n > 0:
            final_price = float(series.iloc[-1])
            pnl = (final_price - entry_price) * position
            equity += pnl
            trades += 1
            wins += 1 if pnl > 0 else 0

        win_rate = (wins / trades) if trades else 0.0
        total_return_pct = ((equity - self.initial_cash) / self.initial_cash * 100.0) if self.initial_cash else 0.0
        return {
            "total_trades": int(trades),
            "win_rate": float(win_rate),
            "final_equity": round(float(equity), 2),
            "total_return_pct": round(float(total_return_pct), 2),
            "strategy": "signal_engine",
        }
