from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

# The stable schema every trade row is normalized to, so the dashboard can rely on these fields
# existing regardless of which execution path produced the entry.
TRADE_FIELDS = [
    "timestamp",
    "symbol",
    "side",
    "strategy",
    "direction",
    "option_type",
    "status",
    "order_id",
    "explanation",
    "market_context",
]


class TradeLog:
    """Append-only trade/decision log backed by a JSON file.

    Normalizes every entry to a fixed schema, deduplicates by order id so the same fill is never logged
    twice, and tolerates a missing or corrupt file by treating it as empty instead of crashing.
    """

    def __init__(self, path: Optional[str | Path] = None):
        if path is None:
            path = Path(__file__).resolve().parents[1] / "data" / "logs" / "trade_history.json"
        self.path = Path(path)

    def _read_raw(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"trades": []}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"trades": []}
        if not isinstance(payload, dict) or not isinstance(payload.get("trades"), list):
            return {"trades": []}
        return payload

    @staticmethod
    def _normalize(entry: Dict[str, Any]) -> Dict[str, Any]:
        return {field: entry.get(field) for field in TRADE_FIELDS}

    def load(self) -> List[Dict[str, Any]]:
        return [self._normalize(trade) for trade in self._read_raw().get("trades", []) if isinstance(trade, dict)]

    def append(self, entry: Dict[str, Any]) -> bool:
        """Append a normalized entry. Returns False (no write) if its order_id is already logged."""
        payload = self._read_raw()
        trades = payload.setdefault("trades", [])
        normalized = self._normalize(entry)

        order_id = normalized.get("order_id")
        if order_id:
            for existing in trades:
                if isinstance(existing, dict) and existing.get("order_id") == order_id:
                    return False

        trades.append(normalized)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return True
