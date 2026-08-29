from __future__ import annotations

from typing import Dict


class StrategySelector:
    """Convert a signal or risk state into an execution-friendly structure."""

    def select_entry_strategy(self, signal: str, symbol: str) -> Dict[str, str]:
        signal = (signal or "neutral").lower()
        if signal == "bullish":
            return {
                "symbol": symbol,
                "direction": "long",
                "option_type": "call",
                "strategy": "long_call",
            }
        if signal == "bearish":
            return {
                "symbol": symbol,
                "direction": "short",
                "option_type": "put",
                "strategy": "long_put",
            }
        return {
            "symbol": symbol,
            "direction": "neutral",
            "option_type": "none",
            "strategy": "hold",
        }

    def select_hedge_strategy(self, risk_score: float, position_direction: str) -> Dict[str, str]:
        risk_score = float(risk_score)
        direction = (position_direction or "neutral").lower()

        if risk_score >= 70:
            strategy = "exit"
            reason = "Risk score is too high; exiting to protect capital."
        elif risk_score >= 45:
            strategy = "protective_put" if direction == "long" else "covered_call"
            reason = "Medium risk detected; hedging exposure with a defensive option structure."
        elif risk_score >= 25:
            strategy = "collar" if direction == "long" else "covered_call"
            reason = "Moderate risk; tightening the position with a partial hedge."
        else:
            strategy = "hold"
            reason = "Risk remains within normal thresholds."

        return {
            "strategy": strategy,
            "reason": reason,
        }
