import pandas as pd

from agent.entry.market_data_agent import MarketDataAgent


class EmptyBarResponse:
    def __init__(self):
        self.data = {}


class EmptyBarClient:
    def get_stock_bars(self, request):
        return EmptyBarResponse()


def test_market_data_agent_uses_fallback_when_response_is_empty():
    agent = MarketDataAgent.__new__(MarketDataAgent)
    agent.client = EmptyBarClient()

    bars = agent.get_bars("AAPL", limit=5, timeframe="1Day")

    assert isinstance(bars, pd.DataFrame)
    assert len(bars) == 5
    assert {"close", "open", "high", "low", "volume"}.issubset(bars.columns)
