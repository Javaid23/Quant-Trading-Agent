from types import SimpleNamespace

import agent.explainer as explainer_module
from agent.explainer import Explainer


RISK = {"risk_score": 42.0, "level": "medium"}
STRATEGY = {"strategy": "long_call"}


def _canned(content):
    def fake_post(url, headers=None, json=None, timeout=None):
        fake_post.url = url
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"choices": [{"message": {"content": content}}]},
        )

    return fake_post


def test_deterministic_fallback_when_no_provider_key():
    explainer = Explainer(groq_api_key="", xai_api_key="", featherless_api_key="")

    text = explainer.explain("bullish", RISK, STRATEGY)

    assert "bullish" in text
    assert "long_call" in text
    assert "42" in text


def test_prefers_groq_when_key_present(monkeypatch):
    explainer = Explainer(groq_api_key="gsk_test", xai_api_key="", featherless_api_key="fk")
    post = _canned("  groq rationale  ")
    monkeypatch.setattr(explainer_module.requests, "post", post)

    text = explainer.explain("bearish", RISK, {"strategy": "long_put"})

    assert text == "groq rationale"
    assert "groq.com" in post.url


def test_xai_key_in_groq_slot_routes_to_xai(monkeypatch):
    # An xAI key (prefix 'xai-') pasted into the Groq slot should be routed to the xAI endpoint.
    explainer = Explainer(groq_api_key="xai-abc123", xai_api_key="")
    post = _canned("grok rationale")
    monkeypatch.setattr(explainer_module.requests, "post", post)

    text = explainer.explain("bullish", RISK, STRATEGY)

    assert text == "grok rationale"
    assert "x.ai" in post.url


def test_uses_featherless_when_only_featherless_key(monkeypatch):
    explainer = Explainer(groq_api_key="", xai_api_key="", featherless_api_key="fk")
    post = _canned("featherless rationale")
    monkeypatch.setattr(explainer_module.requests, "post", post)

    text = explainer.explain("bullish", RISK, STRATEGY)

    assert text == "featherless rationale"
    assert "featherless" in post.url


def test_falls_back_when_api_call_raises(monkeypatch):
    explainer = Explainer(groq_api_key="gsk_test", xai_api_key="")

    def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(explainer_module.requests, "post", boom)

    text = explainer.explain("neutral", RISK, {"strategy": "hold"})

    assert "neutral" in text
    assert "hold" in text


def test_result_is_cached_and_api_called_once(monkeypatch):
    explainer = Explainer(groq_api_key="gsk_test", xai_api_key="")
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
