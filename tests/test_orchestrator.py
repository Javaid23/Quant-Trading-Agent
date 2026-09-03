from types import SimpleNamespace

import pandas as pd

from agent.orchestrator import Orchestrator


def test_orchestrator_no_data_returns_early(monkeypatch):
    orchestrator = Orchestrator()
    entry_called = {"value": False}
    hedge_called = {"value": False}

    monkeypatch.setattr(orchestrator.market_agent, "get_bars", lambda *args, **kwargs: pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"]))

    def fail_entry(*args, **kwargs):
        entry_called["value"] = True
        raise AssertionError("entry strategy should not execute when data is unavailable")

    def fail_hedge(*args, **kwargs):
        hedge_called["value"] = True
        raise AssertionError("hedge strategy should not execute when data is unavailable")

    monkeypatch.setattr(orchestrator.strategy_selector, "select_entry_strategy", fail_entry)
    monkeypatch.setattr(orchestrator.strategy_selector, "select_hedge_strategy", fail_hedge)

    result = orchestrator.evaluate_symbol("AAPL", execute=False)

    assert result["status"] == "no_data"
    assert result["signal"]["signal"] == "no_data"
    assert result["strategy"] is None
    assert result["execution"] is None
    assert not entry_called["value"]
    assert not hedge_called["value"]


def test_orchestrator_uses_live_risk_inputs_and_defense_path(monkeypatch):
    orchestrator = Orchestrator()

    monkeypatch.setattr(
        orchestrator.market_agent,
        "get_bars",
        lambda *args, **kwargs: [{"close": 100.0, "timestamp": "2026-01-01"}],
    )
    monkeypatch.setattr(orchestrator.market_agent, "get_latest_price", lambda *args, **kwargs: 101.0)
    monkeypatch.setattr(
        orchestrator.signal_engine,
        "generate_signal",
        lambda *args, **kwargs: {"signal": "bullish", "score": 80},
    )
    monkeypatch.setattr(
        orchestrator.explainer,
        "explain",
        lambda *args, **kwargs: "Live defense-risk explanation",
    )
    monkeypatch.setattr(
        orchestrator.strategy_selector,
        "select_entry_strategy",
        lambda *args, **kwargs: {"symbol": "AAPL", "direction": "long", "option_type": "call", "strategy": "long_call", "option_symbol": "AAPL260925C00100000"},
    )
    monkeypatch.setattr(
        orchestrator.strategy_selector,
        "select_hedge_strategy",
        lambda risk_score, position_direction, symbol=None, current_price=None: {
            "strategy": "protective_put",
            "option_type": "put",
            "option_symbol": "AAPL260925P00155000",
            "reason": "risk too high",
        },
    )

    monkeypatch.setattr(
        orchestrator.execution_agent,
        "client",
        SimpleNamespace(
            get_account=lambda: SimpleNamespace(equity=1000.0),
            get_all_positions=lambda: [
                {"market_value": "1000", "unrealized_plpc": "-0.50"},
                {"market_value": "0", "unrealized_plpc": "0.00"},
            ],
        ),
    )

    result = orchestrator.evaluate_symbol("AAPL", execute=False)

    assert result["path"] == "defense"
    assert result["risk"]["risk_score"] >= 45
    assert result["risk"]["components"]["delta_exposure"] > 0.9
    assert result["strategy"]["strategy"] == "protective_put"


def test_orchestrator_defense_execute_path_uses_real_option_symbol(monkeypatch):
    orchestrator = Orchestrator()
    captured = {}

    monkeypatch.setattr(
        orchestrator.market_agent,
        "get_bars",
        lambda *args, **kwargs: [{"close": 100.0, "timestamp": "2026-01-01"}],
    )
    monkeypatch.setattr(orchestrator.market_agent, "get_latest_price", lambda *args, **kwargs: 101.0)
    monkeypatch.setattr(
        orchestrator.signal_engine,
        "generate_signal",
        lambda *args, **kwargs: {"signal": "bullish", "score": 80},
    )
    monkeypatch.setattr(
        orchestrator.explainer,
        "explain",
        lambda *args, **kwargs: "Live defense-risk explanation",
    )
    monkeypatch.setattr(
        orchestrator.strategy_selector,
        "select_entry_strategy",
        lambda *args, **kwargs: {"symbol": "AAPL", "direction": "long", "option_type": "call", "strategy": "long_call", "option_symbol": "AAPL260925C00100000"},
    )
    monkeypatch.setattr(
        orchestrator.strategy_selector,
        "get_option_symbol_for_signal",
        lambda symbol, option_type, current_price=None: "AAPL260925P00155000" if option_type == "put" else "AAPL260925C00100000",
    )

    monkeypatch.setattr(
        orchestrator.execution_agent,
        "client",
        SimpleNamespace(
            get_account=lambda: SimpleNamespace(equity=1000.0),
            get_all_positions=lambda: [
                {"market_value": "800", "qty": "1", "side": "long", "cost_basis": "1000", "unrealized_pl": "-200", "unrealized_plpc": "-0.20", "symbol": "AAPL"},
                {"market_value": "0", "qty": "0", "side": "long", "cost_basis": "0", "unrealized_pl": "0", "unrealized_plpc": "0.00", "symbol": "AAPL"},
            ],
        ),
    )

    def fake_execute_strategy(symbol, strategy, qty=1):
        captured["symbol"] = symbol
        captured["strategy"] = strategy
        return {"status": "accepted", "symbol": symbol, "strategy": strategy.get("strategy"), "qty": qty}

    monkeypatch.setattr(orchestrator.execution_agent, "execute_strategy", fake_execute_strategy)

    result = orchestrator.evaluate_symbol("AAPL", execute=True)

    assert result["path"] == "defense"
    assert result["strategy"]["strategy"] == "protective_put"
    assert result["strategy"]["option_symbol"] == "AAPL260925P00155000"
    assert captured["strategy"]["option_symbol"] == "AAPL260925P00155000"
    assert captured["strategy"]["option_symbol"] is not None


def test_orchestrator_execute_true_returns_clear_error_when_execution_unavailable(monkeypatch):
    orchestrator = Orchestrator()
    orchestrator.execution_agent = None

    monkeypatch.setattr(
        orchestrator.market_agent,
        "get_bars",
        lambda *args, **kwargs: [{"close": 100.0, "timestamp": "2026-01-01"}],
    )
    monkeypatch.setattr(orchestrator.market_agent, "get_latest_price", lambda *args, **kwargs: 101.0)
    monkeypatch.setattr(
        orchestrator.signal_engine,
        "generate_signal",
        lambda *args, **kwargs: {"signal": "bullish", "score": 50.0},
    )
    monkeypatch.setattr(
        orchestrator.strategy_selector,
        "select_entry_strategy",
        lambda *args, **kwargs: {"symbol": "AAPL", "direction": "long", "option_type": "call", "strategy": "long_call", "option_symbol": "AAPL260925C00100000"},
    )
    monkeypatch.setattr(
        orchestrator.explainer,
        "explain",
        lambda *args, **kwargs: "No execution agent available",
    )
    monkeypatch.setattr(
        orchestrator.risk_scorer,
        "score_portfolio",
        lambda *args, **kwargs: {"risk_score": 10.0, "level": "low", "components": {"delta_exposure": 0.0, "iv_rank_shift": 0.0, "drawdown_pct": 0.0}},
    )

    result = orchestrator.evaluate_symbol("AAPL", execute=True)

    assert result["execution"]["status"] == "execution_unavailable"
    assert result["execution"]["submitted"] is False
    assert "not configured" in result["execution"]["message"]


def test_orchestrator_neutral_signal_yields_zero_iv_shift(monkeypatch):
    orchestrator = Orchestrator()
    monkeypatch.setattr(orchestrator, "_get_open_positions", lambda: [])
    orchestrator.execution_agent.client = SimpleNamespace(get_account=lambda: SimpleNamespace(equity=1000.0))

    risk_inputs = orchestrator._compute_live_risk_inputs(0.0)

    assert risk_inputs["iv_rank_shift"] == 0.0
