from __future__ import annotations

from typing import Dict


class RiskScorer:
    """Score portfolio risk using a small, explainable heuristic."""

    def score_portfolio(
        self,
        capital_at_risk: float,
        volatility: float,
        drawdown_pct: float,
    ) -> Dict[str, float | str]:
        # `capital_at_risk` is the 0..1 share of equity tied up in open positions (market_value / equity),
        # a capital-exposure proxy -- not true option delta. `volatility` is a 0..1 volatility rank (see
        # indicators.volatility_rank), a real price-derived measure that replaced the old signal-derived one.
        capital_component = min(capital_at_risk * 100.0, 100.0)
        volatility_component = min(volatility * 100.0, 100.0)
        drawdown_component = min(drawdown_pct * 2.5, 100.0)

        risk_score = min(100.0, capital_component * 0.45 + volatility_component * 0.30 + drawdown_component * 0.25)

        if risk_score >= 70:
            level = "high"
        elif risk_score >= 40:
            level = "medium"
        else:
            level = "low"

        return {
            "risk_score": round(float(risk_score), 2),
            "level": level,
            "components": {
                "capital_at_risk": round(float(capital_at_risk), 4),
                "volatility": round(float(volatility), 4),
                "drawdown_pct": round(float(drawdown_pct), 4),
            },
        }
