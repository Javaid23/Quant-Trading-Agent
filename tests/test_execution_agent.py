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
