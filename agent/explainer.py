from __future__ import annotations

import os
from typing import Dict, Optional

import requests
from dotenv import load_dotenv


load_dotenv()


class Explainer:
    """Lightweight plain-language generator for trade explanations."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FEATHERLESS_API_KEY")

    def explain(self, signal: str, risk: Dict[str, object], strategy: Dict[str, str]) -> str:
        if not self.api_key:
            return (
                f"Signal={signal}. "
                f"Risk score={risk.get('risk_score', 'n/a')}. "
                f"Action={strategy.get('strategy', 'hold')}. "
                "This is a deterministic explanation because no LLM key is configured."
            )

        payload = {
            "model": "meta-llama/Meta-Llama-3.1-8B-Instruct",
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
            return data["choices"][0]["message"]["content"].strip()
        except Exception:
            return (
                f"Signal={signal}. Risk indicates {risk.get('level', 'unknown')} risk. "
                f"Strategy selected: {strategy.get('strategy', 'hold')} for a paper trading account."
            )
