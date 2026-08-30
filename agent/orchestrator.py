from __future__ import annotations

from typing import Dict

from agent.defense.risk_scorer import RiskScorer
from agent.entry.market_data_agent import MarketDataAgent
from agent.entry.signal_engine import SignalEngine
from agent.execution_agent import ExecutionAgent
from agent.explainer import Explainer
from agent.strategy_selector import StrategySelector


class Orchestrator:
    """Main loop that coordinates the entry, defense, and execution modules."""

    def __init__(self):
        self.market_agent = MarketDataAgent()
        self.signal_engine = SignalEngine()
        self.risk_scorer = RiskScorer()
        self.strategy_selector = StrategySelector()
        self.explainer = Explainer()
        self.execution_agent = ExecutionAgent()

    def evaluate_symbol(self, symbol: str, execute: bool = False, qty: int = 1) -> Dict[str, object]:
        bars = self.market_agent.get_bars(symbol, limit=120, timeframe="1Day")
        signal = self.signal_engine.generate_signal(bars)
        risk = self.risk_scorer.score_portfolio(
            delta_exposure=0.35,
            iv_rank_shift=12.0,
            drawdown_pct=8.0,
        )
        strategy = self.strategy_selector.select_entry_strategy(signal["signal"], symbol)
        explanation = self.explainer.explain(signal["signal"], risk, strategy)

        execution_result = None
        if execute:
            execution_result = self.execution_agent.execute_strategy(symbol, strategy, qty=qty)

        return {
            "symbol": symbol,
            "signal": signal,
            "risk": risk,
            "strategy": strategy,
            "explanation": explanation,
            "execution": execution_result,
        }


if __name__ == "__main__":
    orchestrator = Orchestrator()
    print(orchestrator.evaluate_symbol("AAPL", execute=False))
