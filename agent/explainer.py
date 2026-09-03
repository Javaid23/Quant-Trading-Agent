from __future__ import annotations

import os
from typing import Dict, Optional, Tuple

import requests
from dotenv import load_dotenv


load_dotenv()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
XAI_URL = "https://api.x.ai/v1/chat/completions"
FEATHERLESS_URL = "https://api.featherless.ai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"
DEFAULT_XAI_MODEL = "grok-3-mini"
# A non-gated model that works on Featherless without a HuggingFace OAuth link (the meta-llama default
# is gated). Override with FEATHERLESS_MODEL.
DEFAULT_FEATHERLESS_MODEL = "Qwen/Qwen2.5-7B-Instruct"


class Explainer:
    """Plain-language generator for trade explanations with a safe deterministic fallback.

    Supports Groq (fast, non-gated free tier), xAI/Grok, and Featherless via their OpenAI-compatible
    chat endpoints, chosen by whichever key is configured. An xAI key (prefix ``xai-``) is detected even
    if it was placed in GROQ_API_KEY. Results are cached per (signal, risk score, strategy) so repeated
    decisions do not spend credits or add latency, and any network/model failure degrades gracefully to a
    deterministic template rather than blocking the agent.
    """

    def __init__(
        self,
        groq_api_key: Optional[str] = None,
        xai_api_key: Optional[str] = None,
        featherless_api_key: Optional[str] = None,
        groq_model: Optional[str] = None,
        xai_model: Optional[str] = None,
        featherless_model: Optional[str] = None,
        api_key: Optional[str] = None,  # backward-compatible alias for the Featherless key
    ):
        self.groq_api_key = groq_api_key if groq_api_key is not None else os.getenv("GROQ_API_KEY")
        self.xai_api_key = xai_api_key if xai_api_key is not None else os.getenv("XAI_API_KEY")
        featherless = featherless_api_key if featherless_api_key is not None else api_key
        self.featherless_api_key = featherless if featherless is not None else os.getenv("FEATHERLESS_API_KEY")
        self.groq_model = groq_model or os.getenv("GROQ_MODEL") or DEFAULT_GROQ_MODEL
        self.xai_model = xai_model or os.getenv("XAI_MODEL") or DEFAULT_XAI_MODEL
        self.featherless_model = featherless_model or os.getenv("FEATHERLESS_MODEL") or DEFAULT_FEATHERLESS_MODEL
        self._cache: Dict[Tuple[str, object, str], str] = {}

    def _provider_chain(self) -> list[Tuple[str, str, str, str]]:
        """Ordered (provider, url, api_key, model) list of every configured provider.

        explain() tries them in order and uses the first that succeeds, so a key that is valid but out of
        credits (e.g. a fresh xAI team) transparently falls through to the next provider.
        """
        chain: list[Tuple[str, str, str, str]] = []
        seen: set[str] = set()

        def add(provider: str, url: str, key: Optional[str], model: str) -> None:
            if key and key not in seen:
                chain.append((provider, url, key, model))
                seen.add(key)

        # An xAI key is sometimes pasted into GROQ_API_KEY by mistake; route it to xAI by its prefix.
        add("xai", XAI_URL, self.xai_api_key, self.xai_model)
        if self.groq_api_key and self.groq_api_key.startswith("xai-"):
            add("xai", XAI_URL, self.groq_api_key, self.xai_model)
        else:
            add("groq", GROQ_URL, self.groq_api_key, self.groq_model)
        add("featherless", FEATHERLESS_URL, self.featherless_api_key, self.featherless_model)
        return chain

    @property
    def provider(self) -> str:
        chain = self._provider_chain()
        return chain[0][0] if chain else "none"

    @staticmethod
    def _deterministic(signal: str, risk: Dict[str, object], strategy: Dict[str, str]) -> str:
        return (
            f"Signal={signal}. "
            f"Risk score={risk.get('risk_score', 'n/a')} ({risk.get('level', 'unknown')}). "
            f"Action={strategy.get('strategy', 'hold')}. "
            "This is a paper trading system and this explanation is deterministic."
        )

    @staticmethod
    def _prompt(signal: str, risk: Dict[str, object], strategy: Dict[str, str]) -> str:
        return (
            f"Explain this trading decision in plain English: "
            f"signal={signal}, risk={risk}, strategy={strategy}. "
            "Keep it to 2 sentences and mention that this is a paper trading system."
        )

    def _call_llm(self, url: str, api_key: str, model: str, prompt: str) -> str:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    def explain(self, signal: str, risk: Dict[str, object], strategy: Dict[str, str]) -> str:
        cache_key = (str(signal), risk.get("risk_score"), str(strategy.get("strategy")))
        if cache_key in self._cache:
            return self._cache[cache_key]

        prompt = self._prompt(signal, risk, strategy)
        result = None
        for _provider, url, api_key, model in self._provider_chain():
            try:
                result = self._call_llm(url, api_key, model, prompt)
                break
            except Exception:
                continue

        if result is None:
            result = self._deterministic(signal, risk, strategy)

        self._cache[cache_key] = result
        return result
