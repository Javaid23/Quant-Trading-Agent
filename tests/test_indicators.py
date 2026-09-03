import pandas as pd

import numpy as np

from agent.entry.indicators import (
    calculate_bollinger_bands,
    calculate_macd,
    calculate_rsi,
    evaluate_market_signal,
    moving_average_crossover,
    realized_volatility,
    volatility_rank,
)


def test_rsi_is_between_0_and_100():
    closes = [100, 102, 101, 103, 104, 105, 103, 102, 101, 98, 97, 96, 95, 97, 100]

    rsi = calculate_rsi(closes, period=14)

    assert len(rsi) == len(closes)
    assert 0 <= rsi[-1] <= 100


def test_bollinger_bands_have_expected_order():
    closes = [100, 101, 102, 103, 104, 105, 104, 103, 102, 101] * 2

    bands = calculate_bollinger_bands(closes, period=5, k=2)

    assert bands["upper"][-1] >= bands["middle"][-1]
    assert bands["middle"][-1] >= bands["lower"][-1]


def test_macd_uses_fast_slow_signal_components():
    closes = [10, 11, 12, 13, 14, 15, 16, 15, 14, 13, 12, 11, 10]

    macd, signal, histogram = calculate_macd(closes, fast=3, slow=5, signal=2)

    assert len(macd) == len(closes)
    assert len(signal) == len(closes)
    assert len(histogram) == len(closes)
    assert abs(histogram[-1] - (macd[-1] - signal[-1])) < 1e-9


def test_moving_average_crossover_detects_alignment():
    closes = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]

    result = moving_average_crossover(closes, fast=3, slow=5)

    assert "fast_ma" in result
    assert "slow_ma" in result
    assert len(result["fast_ma"]) == len(closes)
    assert len(result["slow_ma"]) == len(closes)


def test_signal_evaluation_returns_known_direction():
    bullish = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]
    bearish = [109, 108, 107, 106, 105, 104, 103, 102, 101, 100]

    assert evaluate_market_signal(bullish) == "bullish"
    assert evaluate_market_signal(bearish) == "bearish"


def test_volatility_rank_is_between_0_and_1_and_flags_recent_turbulence():
    calm = list(np.linspace(100, 101, 200))
    volatile = list(100 + np.cumsum(np.tile([5.0, -5.0], 25)))
    rank = volatility_rank(calm + volatile, short_window=20, lookback=252)

    assert 0.0 <= rank <= 1.0
    assert rank > 0.5


def test_volatility_rank_returns_zero_when_history_too_short():
    assert volatility_rank([100, 101, 102], short_window=20) == 0.0


def test_realized_volatility_is_positive_for_moving_series():
    prices = list(100 + np.cumsum(np.tile([1.0, -1.0], 30)))
    vol = realized_volatility(prices, window=20)

    assert vol > 0
