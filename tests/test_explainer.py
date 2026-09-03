from types import SimpleNamespace

import agent.explainer as explainer_module
from agent.explainer import Explainer


RISK = {"risk_score": 42.0, "level": "medium"}
STRATEGY = {"strategy": "long_call"}


def test_deterministic_fallback_when_no_api_key():
    explainer = Explainer(api_key=None)

    text = explainer.explain("bullish", RISK, STRATEGY)

    assert "bullish" in text
    assert "long_call" in text
    assert "42" in text


def test_uses_api_response_when_key_present(monkeypatch):
    explainer = Explainer(api_key="test-key")

    def fake_post(url, headers=None, json=None, timeout=None):
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"choices": [{"message": {"content": "  A concise paper-trading rationale.  "}}]},
        )

    monkeypatch.setattr(explainer_module.requests, "post", fake_post)

    text = explainer.explain("bearish", RISK, {"strategy": "long_put"})

    assert text == "A concise paper-trading rationale."


def test_falls_back_when_api_call_raises(monkeypatch):
    explainer = Explainer(api_key="test-key")

    def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(explainer_module.requests, "post", boom)

    text = explainer.explain("neutral", RISK, {"strategy": "hold"})

    assert "neutral" in text
    assert "hold" in text


def test_result_is_cached_and_api_called_once(monkeypatch):
    explainer = Explainer(api_key="test-key")
    calls = {"count": 0}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["count"] += 1
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"choices": [{"message": {"content": "cached rationale"}}]},
        )

    monkeypatch.setattr(explainer_module.requests, "post", fake_post)

    first = explainer.explain("bullish", RISK, STRATEGY)
    second = explainer.explain("bullish", RISK, STRATEGY)

    assert first == second == "cached rationale"
    assert calls["count"] == 1
