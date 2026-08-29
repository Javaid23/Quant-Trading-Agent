from __future__ import annotations

from typing import Dict

from agent.defense.risk_scorer import RiskScorer
from agent.entry.market_data_agent import MarketDataAgent
from agent.entry.signal_engine import SignalEngine
from agent.explainer import Explainer
from agent.strategy_selector import StrategySelector


class Orchestrator:
    """Main loop that coordinates the entry and defense modules."""

    def __init__(self):
        self.market_agent = MarketDataAgent()
        self.signal_engine = SignalEngine()
        self.risk_scorer = RiskScorer()
        self.strategy_selector = StrategySelector()
        self.explainer = Explainer()

    def evaluate_symbol(self, symbol: str) -> Dict[str, object]:
        bars = self.market_agent.get_bars(symbol, limit=120, timeframe="1Day")
        signal = self.signal_engine.generate_signal(bars)
        risk = self.risk_scorer.score_portfolio(
            delta_exposure=0.35,
            iv_rank_shift=12.0,
            drawdown_pct=8.0,
        )
        strategy = self.strategy_selector.select_entry_strategy(signal["signal"], symbol)
        explanation = self.explainer.explain(signal["signal"], risk, strategy)

        return {
            "symbol": symbol,
            "signal": signal,
            "risk": risk,
            "strategy": strategy,
            "explanation": explanation,
        }


if __name__ == "__main__":
    orchestrator = Orchestrator()
    print(orchestrator.evaluate_symbol("AAPL"))
