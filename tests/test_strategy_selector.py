from datetime import date, timedelta

from agent.execution_agent import ExecutionAgent
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

    hedge = selector.select_hedge_strategy(80, "long", symbol="AAPL", current_price=200.0)

    assert hedge["strategy"] in {"protective_put", "covered_call", "exit"}
    assert hedge["option_type"] in {"put", "call", "none"}
    assert hedge["reason"]
    assert hedge["option_symbol"] is None or isinstance(hedge["option_symbol"], str)


def test_execution_agent_routes_hedge_to_option_order(monkeypatch):
    agent = ExecutionAgent()
    captured = {}

    def fake_place_option_order(option_symbol, qty, side, option_type):
        captured["kind"] = "option"
        captured["option_symbol"] = option_symbol
        captured["qty"] = qty
        captured["side"] = side
        captured["option_type"] = option_type
        return {"status": "accepted", "symbol": option_symbol, "side": side, "qty": qty}

    def fail_stock_order(*args, **kwargs):
        raise AssertionError("stock market order should not be used for protective put hedge")

    monkeypatch.setattr(agent, "place_option_order", fake_place_option_order)
    monkeypatch.setattr(agent, "place_market_order", fail_stock_order)

    strategy = {
        "strategy": "protective_put",
        "option_type": "put",
        "option_symbol": "AAPL260925P00155000",
        "reason": "Risk is elevated; buy protective put.",
    }

    result = agent.execute_strategy("AAPL", strategy, qty=2)

    assert captured["kind"] == "option"
    assert captured["option_symbol"] == "AAPL260925P00155000"
    assert captured["side"] == "buy"
    assert result["status"] == "accepted"
