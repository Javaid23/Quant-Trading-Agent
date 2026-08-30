from datetime import date, timedelta

from agent.strategy_selector import StrategySelector


def test_strategy_selector_uses_real_contract_dict_from_option_chain():
    selector = StrategySelector()
    today = date.today()
    near_exp = (today + timedelta(days=10)).strftime("%Y-%m-%d")
    valid_exp = (today + timedelta(days=21)).strftime("%Y-%m-%d")
    chosen_symbol = "AAPL261218C00240000"

    class FakeChain:
        option_contracts = {
            "AAPL261218C00240000": {
                "symbol": chosen_symbol,
                "expiration": valid_exp,
                "strike_price": 240.0,
                "type": "call",
            },
            "AAPL261218C00500000": {
                "symbol": "AAPL261218C00500000",
                "expiration": valid_exp,
                "strike_price": 500.0,
                "type": "call",
            },
            "AAPL260903C00480000": {
                "symbol": "AAPL260903C00480000",
                "expiration": near_exp,
                "strike_price": 480.0,
                "type": "call",
            },
        }

    class FakeClient:
        def get_option_chain(self, request):
            return FakeChain()

    selector.option_client = FakeClient()

    selected = selector.get_option_symbol_for_signal("AAPL", "call", current_price=220.0)

    assert selected == chosen_symbol


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
