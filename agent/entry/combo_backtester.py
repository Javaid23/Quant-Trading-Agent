from __future__ import annotations

from itertools import combinations
from typing import Dict, List, Mapping, Sequence

import numpy as np
import pandas as pd

from agent.entry.indicators import (
    calculate_bollinger_bands,
    calculate_macd,
    calculate_rsi,
    moving_average_crossover,
)

# The four indicators the live SignalEngine blends, with the same signed weights it uses, so the
# selection study describes the very strategy that trades rather than a parallel one.
INDICATORS = ("rsi", "macd", "bollinger", "ma")
# Mirrors SignalEngine's weights so the study describes the strategy that actually trades.
WEIGHTS = {"rsi": 20.0, "macd": 10.0, "bollinger": 20.0, "ma": 15.0}


def _component_scores(closes: pd.Series) -> Dict[str, np.ndarray]:
    """Return the per-bar signed contribution of each indicator, matching SignalEngine's rules."""
    rsi = calculate_rsi(closes, 14)
    macd, signal_line, _ = calculate_macd(closes, 12, 26, 9)
    bands = calculate_bollinger_bands(closes, 20)
    ma = moving_average_crossover(closes, fast=3, slow=5)
    close_arr = closes.to_numpy(dtype=float)

    return {
        "rsi": np.where(rsi < 30, WEIGHTS["rsi"], np.where(rsi > 70, -WEIGHTS["rsi"], 0.0)),
        "macd": np.where(macd > signal_line, WEIGHTS["macd"], -WEIGHTS["macd"]),
        "bollinger": np.where(close_arr > bands["middle"], WEIGHTS["bollinger"], -WEIGHTS["bollinger"]),
        "ma": np.where(ma["fast_ma"] > ma["slow_ma"], WEIGHTS["ma"], -WEIGHTS["ma"]),
    }


class ComboBacktester:
    """Test every combination of indicators on historical prices and rank them.

    Position model mirrors the live agent's directional view: go long on a bullish score, short on a
    bearish score, flat on neutral, flipping when the score changes. P&L is measured on the underlying
    move (the directional edge), which is what we want when comparing indicator combinations.
    """

    def __init__(self, initial_cash: float = 10000.0, warmup: int = 26, deadband_frac: float = 0.2):
        self.initial_cash = float(initial_cash)
        self.warmup = int(warmup)
        self.deadband_frac = float(deadband_frac)

    def _combo_signals(self, scores: Mapping[str, np.ndarray], combo: Sequence[str]) -> np.ndarray:
        enabled_max = sum(WEIGHTS[key] for key in combo)
        deadband = self.deadband_frac * enabled_max
        total = np.zeros_like(next(iter(scores.values())), dtype=float)
        for key in combo:
            total = total + scores[key]
        signals = np.where(total > deadband, 1, np.where(total < -deadband, -1, 0)).astype(int)
        # Suppress the warm-up region where MACD/Bollinger/MA are not yet well-defined.
        if self.warmup > 0:
            signals[: self.warmup] = 0
        return signals

    def _simulate(self, signals: np.ndarray, closes: pd.Series) -> Dict[str, float | int]:
        trades = 0
        wins = 0
        position = 0
        entry_price = 0.0
        # Collect each trade's percentage move so results are position-size independent and directly
        # comparable across tickers of very different prices, and so we can derive Sharpe / drawdown.
        trade_returns: list[float] = []
        n = len(closes)

        def record(exit_price: float) -> None:
            nonlocal trades, wins
            if entry_price > 0:
                trade_ret = (exit_price - entry_price) / entry_price * position * 100.0
                trade_returns.append(trade_ret)
                trades += 1
                wins += 1 if trade_ret > 0 else 0

        for i in range(n):
            price = float(closes.iloc[i])
            desired = int(signals[i])
            if position != 0 and desired != position:
                record(price)
                position = 0
            if position == 0 and desired != 0:
                position = desired
                entry_price = price

        if position != 0 and n > 0:
            record(float(closes.iloc[-1]))

        win_rate = (wins / trades) if trades else 0.0
        cum_return_pct = float(np.sum(trade_returns)) if trade_returns else 0.0

        # Risk-adjusted return: mean per-trade return over its volatility, scaled by sqrt(#trades).
        if len(trade_returns) >= 2:
            arr = np.asarray(trade_returns, dtype=float)
            std = float(arr.std(ddof=1))
            sharpe = float(arr.mean() / std * np.sqrt(len(arr))) if std > 1e-9 else 0.0
        else:
            sharpe = 0.0

        # Max drawdown of the cumulative-return equity curve (in percentage points).
        curve = np.concatenate([[0.0], np.cumsum(trade_returns)]) if trade_returns else np.array([0.0])
        peak = np.maximum.accumulate(curve)
        max_drawdown = float((curve - peak).min())

        final_equity = self.initial_cash * (1 + cum_return_pct / 100.0)
        return {
            "total_trades": int(trades),
            "win_rate": float(win_rate),
            "final_equity": round(float(final_equity), 2),
            "total_return_pct": float(cum_return_pct),
            "sharpe": round(sharpe, 2),
            "max_drawdown_pct": round(max_drawdown, 2),
        }

    def run_combo(
        self, closes: Sequence[float] | pd.Series, combo: Sequence[str], oos_from: float | None = None
    ) -> Dict[str, float | int]:
        series = pd.Series(closes, dtype=float).reset_index(drop=True)
        if len(series) <= self.warmup:
            return {"total_trades": 0, "win_rate": 0.0, "final_equity": self.initial_cash, "total_return_pct": 0.0, "sharpe": 0.0, "max_drawdown_pct": 0.0}
        scores = _component_scores(series)
        signals = self._combo_signals(scores, combo)
        if oos_from is not None:
            # Out-of-sample: indicators are warmed on the whole series, but only trades placed in the
            # last (1 - oos_from) of the data count -- i.e. on data the strategy was not "chosen" on.
            cut = max(int(len(series) * float(oos_from)), self.warmup)
            signals[:cut] = 0
        return self._simulate(signals, series)

    @staticmethod
    def all_combos() -> List[tuple[str, ...]]:
        return [combo for size in range(1, len(INDICATORS) + 1) for combo in combinations(INDICATORS, size)]

    def run_selection(
        self, price_map: Mapping[str, Sequence[float] | pd.Series], oos_from: float | None = None
    ) -> List[Dict[str, object]]:
        """Run every indicator combination across all symbols and return them ranked best-first.

        Pass oos_from (e.g. 0.7) to evaluate only out-of-sample trades placed in the final portion of
        each series, which is the honest way to report performance the strategy was not fitted on.
        """
        results: List[Dict[str, object]] = []
        for combo in self.all_combos():
            per_symbol = [self.run_combo(closes, combo, oos_from=oos_from) for closes in price_map.values()]
            count = len(per_symbol) or 1
            avg_return = sum(m["total_return_pct"] for m in per_symbol) / count
            avg_win_rate = sum(m["win_rate"] for m in per_symbol) / count
            avg_sharpe = sum(m.get("sharpe", 0.0) for m in per_symbol) / count
            worst_drawdown = min((m.get("max_drawdown_pct", 0.0) for m in per_symbol), default=0.0)
            total_trades = sum(m["total_trades"] for m in per_symbol)
            results.append({
                "combo": "+".join(combo),
                "indicators": list(combo),
                "avg_return_pct": round(avg_return, 2),
                "avg_win_rate": round(avg_win_rate, 3),
                "avg_sharpe": round(avg_sharpe, 2),
                "worst_drawdown_pct": round(worst_drawdown, 2),
                "total_trades": int(total_trades),
                "symbols_tested": len(price_map),
            })

        results.sort(key=lambda row: (row["avg_sharpe"], row["avg_return_pct"]), reverse=True)
        return results
