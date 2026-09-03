from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional


class ExitManager:
    """Decide when to close an open position: take-profit, stop-loss, or near-expiry.

    This is the piece that turns the agent from "buy options and hold to zero" into something that
    actively manages the book. Every decision is deterministic and carries a plain-language reason so it
    stays explainable. Thresholds are expressed as fractions of unrealized P&L (0.5 == 50%).
    """

    def __init__(
        self,
        take_profit_pct: float = 0.5,
        stop_loss_pct: float = 0.5,
        min_days_to_expiry: int = 3,
    ):
        self.take_profit_pct = float(take_profit_pct)
        self.stop_loss_pct = float(stop_loss_pct)
        self.min_days_to_expiry = int(min_days_to_expiry)

    @staticmethod
    def _is_option_symbol(symbol: str) -> bool:
        s = (symbol or "").upper().strip()
        return len(s) >= 19 and s[-9] in {"C", "P"} and s[-15:-9].isdigit() and s[-8:].isdigit()

    @classmethod
    def _parse_expiry(cls, option_symbol: str) -> Optional[date]:
        s = (option_symbol or "").upper().strip()
        if not cls._is_option_symbol(s):
            return None
        try:
            return datetime.strptime(s[-15:-9], "%y%m%d").date()
        except ValueError:
            return None

    @staticmethod
    def _get(position: Any, key: str, default: Any = None) -> Any:
        if isinstance(position, dict):
            return position.get(key, default)
        return getattr(position, key, default)

    def evaluate_position(self, position: Any, today: Optional[date] = None) -> Dict[str, Any]:
        today = today or date.today()
        symbol = str(self._get(position, "symbol", "") or "")

        plpc_raw = self._get(position, "unrealized_plpc", None)
        try:
            plpc = float(plpc_raw) if plpc_raw is not None else None
        except (TypeError, ValueError):
            plpc = None

        expiry = self._parse_expiry(symbol)
        days_to_expiry = (expiry - today).days if expiry is not None else None

        action = "hold"
        reason = "Within profit, loss, and time thresholds; holding."

        # Priority: cut losses first, then lock in gains, then avoid expiration risk.
        if plpc is not None and plpc <= -self.stop_loss_pct:
            action = "stop_loss"
            reason = (
                f"Loss {plpc * 100:.1f}% breached the stop-loss of -{self.stop_loss_pct * 100:.0f}%; "
                "closing to protect capital."
            )
        elif plpc is not None and plpc >= self.take_profit_pct:
            action = "take_profit"
            reason = (
                f"Gain {plpc * 100:.1f}% reached the take-profit of +{self.take_profit_pct * 100:.0f}%; "
                "locking in the win."
            )
        elif days_to_expiry is not None and days_to_expiry <= self.min_days_to_expiry:
            action = "expiry_exit"
            reason = (
                f"{days_to_expiry} day(s) to expiry (<= {self.min_days_to_expiry}); "
                "closing to avoid expiration risk and terminal time decay."
            )

        return {
            "symbol": symbol,
            "action": action,
            "reason": reason,
            "unrealized_plpc": plpc,
            "days_to_expiry": days_to_expiry,
            "is_option": self._is_option_symbol(symbol),
            "should_close": action != "hold",
        }

    def evaluate_portfolio(self, positions: List[Any], today: Optional[date] = None) -> List[Dict[str, Any]]:
        return [self.evaluate_position(position, today=today) for position in (positions or [])]
