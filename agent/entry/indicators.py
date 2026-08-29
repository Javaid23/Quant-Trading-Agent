from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


def calculate_rsi(closes: List[float] | np.ndarray | pd.Series, period: int = 14) -> np.ndarray:
    """Return RSI values for the given close series."""
    closes = pd.Series(closes, dtype=float)
    if len(closes) < period + 1:
        return np.full(len(closes), 50.0, dtype=float)

    delta = closes.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    avg_gain = gains.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(50.0)
    return rsi.to_numpy(dtype=float)


def calculate_bollinger_bands(
    closes: List[float] | np.ndarray | pd.Series,
    period: int = 20,
    k: float = 2.0,
) -> Dict[str, np.ndarray]:
    """Compute Bollinger Bands with a rolling mean and standard deviation."""
    closes = pd.Series(closes, dtype=float)

    middle = closes.rolling(window=period, min_periods=period).mean()
    std = closes.rolling(window=period, min_periods=period).std(ddof=0)
    upper = middle + k * std
    lower = middle - k * std

    return {
        "middle": middle.to_numpy(dtype=float),
        "upper": upper.to_numpy(dtype=float),
        "lower": lower.to_numpy(dtype=float),
    }


def calculate_macd(
    closes: List[float] | np.ndarray | pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return MACD line, signal line, and histogram arrays."""
    closes = pd.Series(closes, dtype=float)

    fast_ema = closes.ewm(span=fast, adjust=False).mean()
    slow_ema = closes.ewm(span=slow, adjust=False).mean()
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return macd_line.to_numpy(dtype=float), signal_line.to_numpy(dtype=float), histogram.to_numpy(dtype=float)


def moving_average_crossover(
    closes: List[float] | np.ndarray | pd.Series,
    fast: int = 10,
    slow: int = 30,
) -> Dict[str, np.ndarray]:
    """Compute fast and slow moving-average values for crossover analysis."""
    closes = pd.Series(closes, dtype=float)
    fast_ma = closes.rolling(window=fast, min_periods=fast).mean()
    slow_ma = closes.rolling(window=slow, min_periods=slow).mean()
    return {
        "fast_ma": fast_ma.to_numpy(dtype=float),
        "slow_ma": slow_ma.to_numpy(dtype=float),
    }


def evaluate_market_signal(closes: List[float] | np.ndarray | pd.Series) -> str:
    """Simple directional heuristic based on the latest close trend."""
    series = pd.Series(closes, dtype=float)
    if len(series) < 2:
        return "neutral"

    latest = series.iloc[-1]
    prior = series.iloc[-2]
    if latest > prior:
        return "bullish"
    if latest < prior:
        return "bearish"
    return "neutral"


if __name__ == "__main__":
    sample = [100, 101, 102, 99, 103, 105, 104, 106, 108, 110]
    print(calculate_rsi(sample))
    print(calculate_bollinger_bands(sample))
    print(calculate_macd(sample))
    print(moving_average_crossover(sample))
    print(evaluate_market_signal(sample))
