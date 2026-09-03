from __future__ import annotations

import os
from typing import Dict, Optional, Tuple

import requests
from dotenv import load_dotenv


load_dotenv()


class Explainer:
    """Plain-language generator for trade explanations, backed by Featherless with a safe fallback.

    Results are cached per (signal, risk score, strategy) so repeated identical decisions do not spend
    API credits or add latency during a live demo. If no key is configured or the call fails, a
    deterministic explanation is returned instead so the agent never blocks on the network.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct"):
        self.api_key = api_key or os.getenv("FEATHERLESS_API_KEY")
        self.model = model
        self._cache: Dict[Tuple[str, object, str], str] = {}

    @staticmethod
    def _deterministic(signal: str, risk: Dict[str, object], strategy: Dict[str, str]) -> str:
        return (
            f"Signal={signal}. "
            f"Risk score={risk.get('risk_score', 'n/a')} ({risk.get('level', 'unknown')}). "
            f"Action={strategy.get('strategy', 'hold')}. "
            "This is a paper trading system and this explanation is deterministic."
        )

    def explain(self, signal: str, risk: Dict[str, object], strategy: Dict[str, str]) -> str:
        cache_key = (str(signal), risk.get("risk_score"), str(strategy.get("strategy")))
        if cache_key in self._cache:
            return self._cache[cache_key]

        if not self.api_key:
            result = self._deterministic(signal, risk, strategy)
            self._cache[cache_key] = result
            return result

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Explain this trading decision in plain English: "
                        f"signal={signal}, risk={risk}, strategy={strategy}. "
                        "Keep it to 2 sentences and mention that this is a paper trading system."
                    ),
                }
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                "https://api.featherless.ai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
            result = data["choices"][0]["message"]["content"].strip()
        except Exception:
            result = self._deterministic(signal, risk, strategy)

        self._cache[cache_key] = result
        return result
