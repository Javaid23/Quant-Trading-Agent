from agent.strategy_selector import StrategySelector


def test_strategy_selector_uses_bullish_or_bearish_view():
    selector = StrategySelector()

    bullish = selector.select_entry_strategy("bullish", "AAPL")
    bearish = selector.select_entry_strategy("bearish", "AAPL")

    assert bullish["direction"] == "long"
    assert bearish["direction"] == "short"
    assert bullish["option_type"] in {"call", "put"}
    assert bearish["option_type"] in {"call", "put"}


def test_strategy_selector_chooses_defensive_hedge():
    selector = StrategySelector()

    hedge = selector.select_hedge_strategy(80, "long")

    assert hedge["strategy"] in {"protective_put", "covered_call", "collar", "exit"}
    assert hedge["reason"]
