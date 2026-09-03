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
