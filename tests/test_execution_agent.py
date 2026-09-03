from types import SimpleNamespace

from agent.execution_agent import ExecutionAgent


def test_execution_agent_blocks_option_orders_when_market_closed():
    agent = ExecutionAgent.__new__(ExecutionAgent)
    agent.client = SimpleNamespace(
        get_clock=lambda: SimpleNamespace(
            is_open=False,
            next_open="2026-08-31T09:30:00-04:00",
            next_close="2026-08-31T16:00:00-04:00",
        ),
        submit_order=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("submit_order should not be called when the market is closed")
        ),
    )

    result = agent.place_option_order("AAPL260918C00220000", 1, "buy", option_type="call")

    assert result["status"] == "not_submitted"
    assert result["market_status"] == "closed"
    assert "Markets are currently closed" in result["message"]
    assert "Next open" in result["message"]


def test_execution_agent_close_fallback_uses_limit_order_and_infers_option_type(monkeypatch):
    agent = ExecutionAgent.__new__(ExecutionAgent)
    captured = {}

    class FakeClient:
        def close_position(self, symbol_or_asset_id):
            raise RuntimeError("No available quote for this option")

        def place_option_order(self, **kwargs):
            captured.update(kwargs)
            return {"id": "order-123", "status": "accepted", "symbol": kwargs["option_symbol"]}

    agent.client = FakeClient()
    monkeypatch.setattr(agent, "_get_option_last_price", lambda option_symbol: 1.23)

    result = agent.close_option_position_with_limit_fallback("AAPL260918C00220000", qty=2)

    assert captured["type"] == "limit"
    assert captured["time_in_force"] == "day"
    assert captured["position_intent"] == "sell_to_close"
    assert captured["limit_price"] == 1.23
    assert captured["option_type"] == "call"
    assert result["order_type"] == "sell_to_close_limit"
    assert result["retry_used"] is True


def test_execution_exit_closes_existing_option_and_never_opens_short(monkeypatch):
    agent = ExecutionAgent.__new__(ExecutionAgent)
    closed = {}

    class FakeClient:
        def get_all_positions(self):
            return [
                {"symbol": "AAPL260925P00325000", "qty": "1", "side": "long"},
                {"symbol": "MSFT260925P00485000", "qty": "1", "side": "long"},
            ]

        def close_position(self, symbol_or_asset_id):
            raise AssertionError("stock close should not be used for an option position")

    agent.client = FakeClient()

    def fake_close_opt(option_symbol, qty=1):
        closed["symbol"] = option_symbol
        return {"symbol": option_symbol, "order_type": "sell_to_close_market", "submitted": True, "status": "accepted"}

    monkeypatch.setattr(agent, "close_option_position_with_limit_fallback", fake_close_opt)

    def fail_market(*args, **kwargs):
        raise AssertionError("exit must never place a market order that could open a new position")

    monkeypatch.setattr(agent, "place_market_order", fail_market)

    result = agent.execute_strategy("AAPL", {"strategy": "exit", "option_type": "none", "option_symbol": None}, qty=1)

    assert result["status"] == "exit_submitted"
    assert result["submitted"] is True
    # Only the AAPL contract should be closed, not the unrelated MSFT one.
    assert closed["symbol"] == "AAPL260925P00325000"


def test_execution_exit_with_no_position_places_no_order(monkeypatch):
    agent = ExecutionAgent.__new__(ExecutionAgent)

    class FakeClient:
        def get_all_positions(self):
            return [{"symbol": "TSLA260925P00100000", "qty": "1", "side": "long"}]

        def close_position(self, symbol_or_asset_id):
            raise AssertionError("nothing to close for AAPL")

    agent.client = FakeClient()

    def fail_market(*args, **kwargs):
        raise AssertionError("must not place a market order when there is no position to exit")

    monkeypatch.setattr(agent, "place_market_order", fail_market)

    result = agent.execute_strategy("AAPL", {"strategy": "exit", "option_type": "none", "option_symbol": None}, qty=1)

    assert result["status"] == "no_position"
    assert result["submitted"] is False
