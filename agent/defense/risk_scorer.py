from __future__ import annotations

from typing import Dict


class RiskScorer:
    """Score portfolio risk using a small, explainable heuristic."""

    def score_portfolio(
        self,
        delta_exposure: float,
        iv_rank_shift: float,
        drawdown_pct: float,
    ) -> Dict[str, float | str]:
        delta_component = min(delta_exposure * 100.0, 100.0)
        iv_component = min(iv_rank_shift * 2.0, 100.0)
        drawdown_component = min(drawdown_pct * 2.5, 100.0)

        risk_score = min(100.0, delta_component * 0.45 + iv_component * 0.30 + drawdown_component * 0.25)

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
                "delta_exposure": round(float(delta_exposure), 4),
                "iv_rank_shift": round(float(iv_rank_shift), 4),
                "drawdown_pct": round(float(drawdown_pct), 4),
            },
        }
