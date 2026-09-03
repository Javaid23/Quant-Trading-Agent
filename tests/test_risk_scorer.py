from agent.defense.risk_scorer import RiskScorer


def test_risk_score_rises_with_more_risk():
    scorer = RiskScorer()

    low = scorer.score_portfolio(delta_exposure=0.2, volatility=0.1, drawdown_pct=5)
    high = scorer.score_portfolio(delta_exposure=0.8, volatility=0.8, drawdown_pct=22)

    assert 0 <= low["risk_score"] <= 100
    assert 0 <= high["risk_score"] <= 100
    assert high["risk_score"] > low["risk_score"]
    assert high["level"] in {"medium", "high"}
