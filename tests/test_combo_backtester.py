import numpy as np

from agent.entry.combo_backtester import ComboBacktester


def test_all_combos_are_fifteen():
    assert len(ComboBacktester.all_combos()) == 15


def test_run_combo_returns_expected_keys():
    prices = list(np.linspace(100, 140, 80))
    result = ComboBacktester().run_combo(prices, ("rsi", "macd", "bollinger", "ma"))

    assert set(result) == {"total_trades", "win_rate", "final_equity", "total_return_pct"}


def test_uptrend_is_profitable_for_trend_following_combo():
    # A steady uptrend should be caught long by the MACD + MA trend combination.
    prices = list(np.linspace(100, 200, 120))
    result = ComboBacktester().run_combo(prices, ("macd", "ma"))

    assert result["total_return_pct"] > 0
    assert result["total_trades"] >= 1


def test_run_selection_ranks_and_covers_all_combos():
    up = list(np.linspace(100, 200, 120))
    down = list(np.linspace(200, 120, 120))
    price_map = {"UP": up, "DOWN": down}

    results = ComboBacktester().run_selection(price_map)

    assert len(results) == 15
    # Sorted best-first by average return.
    returns = [row["avg_return_pct"] for row in results]
    assert returns == sorted(returns, reverse=True)
    assert all(row["symbols_tested"] == 2 for row in results)


def test_series_shorter_than_warmup_returns_zero_trades():
    result = ComboBacktester(warmup=26).run_combo([100, 101, 102], ("rsi",))

    assert result["total_trades"] == 0
    assert result["total_return_pct"] == 0.0
