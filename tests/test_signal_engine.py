import pandas as pd

from agent.entry.backtester import Backtester
from agent.entry.signal_engine import SignalEngine


def test_backtester_returns_summary():
    prices = pd.Series([100, 101, 102, 103, 104, 105, 106, 105, 107, 108, 109, 110])

    result = Backtester().run(prices)

    assert "total_trades" in result
    assert "win_rate" in result
    assert "final_equity" in result
    assert result["total_trades"] >= 0


def test_signal_engine_generates_bullish_or_bearish_signal():
    data = pd.DataFrame({
        "close": [100, 101, 102, 103, 104, 105, 106, 108, 110, 112, 114, 116],
        "volume": [200] * 12,
    })

    signal = SignalEngine().generate_signal(data)

    assert signal["signal"] in {"bullish", "bearish", "neutral"}
    assert signal["score"] >= -100
    assert signal["score"] <= 100


def test_signal_engine_flags_flat_or_short_series_as_no_data():
    flat = pd.DataFrame({"close": [100.0] * 5, "volume": [200] * 5})
    short = pd.DataFrame({"close": [100.0, 100.0, 100.0, 100.0], "volume": [200] * 4})

    assert SignalEngine().generate_signal(flat)["signal"] == "no_data"
    assert SignalEngine().generate_signal(short)["signal"] == "no_data"
