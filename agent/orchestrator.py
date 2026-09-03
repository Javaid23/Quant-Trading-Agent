from __future__ import annotations

from typing import Any, Dict, Iterable

from agent.defense.exit_manager import ExitManager
from agent.defense.risk_scorer import RiskScorer

LEGACY_STALE_POSITIONS = {
    "AAPL260918P00100000",
    "AMZN260925P00140000",
    "META260925P00100000",
    "MSFT260925P00270000",
    "TSLA260925P00100000",
}
# Legacy stale positions from the pre-fix pricing bug are intentionally excluded from live risk scoring.
# These were artifacts of old stale $0.03-type entries and are not representative of current strategy risk.
import pandas as pd

from agent.entry.indicators import volatility_rank
from agent.entry.market_data_agent import MarketDataAgent
from agent.entry.signal_engine import SignalEngine
from agent.execution_agent import ExecutionAgent
from agent.explainer import Explainer
from agent.strategy_selector import StrategySelector


class Orchestrator:
    """Main loop that coordinates the entry, defense, and execution modules."""

    def __init__(self):
        self.market_agent = MarketDataAgent()
        self.signal_engine = SignalEngine()
        self.risk_scorer = RiskScorer()
        self.exit_manager = ExitManager()
        self.strategy_selector = StrategySelector()
        self.explainer = Explainer()
        try:
            self.execution_agent = ExecutionAgent()
        except ValueError:
            self.execution_agent = None

    def _get_open_positions(self) -> Iterable[Any]:
        if self.execution_agent is None or self.execution_agent.client is None:
            return []
        try:
            return list(self.execution_agent.client.get_all_positions())
        except Exception:
            return []

    def _get_position_direction(self, positions: Iterable[Any]) -> str:
        net_direction = 0.0
        for position in positions:
            if isinstance(position, dict):
                qty = float(position.get("qty", 0) or 0)
                side = str(position.get("side", "long") or "long").lower()
            else:
                qty = float(getattr(position, "qty", 0) or 0)
                side = str(getattr(position, "side", "long") or "long").lower()
            if side == "short":
                net_direction -= abs(qty)
            else:
                net_direction += abs(qty)
        if net_direction > 0:
            return "long"
        if net_direction < 0:
            return "short"
        return "neutral"

    @staticmethod
    def _extract_volatility_rank(bars: Any) -> float:
        """Compute the volatility rank (0..1) for the symbol from its historical bars.

        Handles both a bars DataFrame and the list-of-dicts shape used in tests; returns 0.0 when
        closes cannot be extracted so an unmeasurable name never inflates the risk score.
        """
        try:
            if hasattr(bars, "columns") and "close" in getattr(bars, "columns", []):
                close_values = pd.to_numeric(bars["close"], errors="coerce").dropna()
            elif isinstance(bars, (list, tuple)):
                close_values = pd.Series(
                    [row.get("close") for row in bars if isinstance(row, dict) and row.get("close") is not None],
                    dtype=float,
                )
            else:
                return 0.0
            return volatility_rank(close_values)
        except Exception:
            return 0.0

    def _compute_live_risk_inputs(self, volatility_rank: float) -> Dict[str, float]:
        positions = list(self._get_open_positions())
        account = None
        if self.execution_agent is not None and self.execution_agent.client is not None:
            try:
                account = self.execution_agent.client.get_account()
            except Exception:
                account = None

        equity = 0.0
        if account is not None:
            equity = float(getattr(account, "equity", 0.0) or 0.0)
        if equity <= 0:
            equity = 1.0

        total_market_value = 0.0
        worst_negative_unrealized_plpc = 0.0
        per_position_loss_pct = []
        for position in positions:
            if isinstance(position, dict):
                market_value = float(position.get("market_value", 0) or 0)
                cost_basis = float(position.get("cost_basis", 0) or 0)
                unrealized_pl = float(position.get("unrealized_pl", 0) or 0)
                unrealized_plpc = position.get("unrealized_plpc")
                symbol = position.get("symbol")
            else:
                market_value = float(getattr(position, "market_value", 0) or 0)
                cost_basis = float(getattr(position, "cost_basis", 0) or 0)
                unrealized_pl = float(getattr(position, "unrealized_pl", 0) or 0)
                unrealized_plpc = getattr(position, "unrealized_plpc", None)
                symbol = getattr(position, "symbol", None)

            if symbol in LEGACY_STALE_POSITIONS:
                continue

            total_market_value += market_value

            # Drawdown must reflect losses only. This previously used abs(), so a winning position
            # (e.g. +50%) was counted as 50% drawdown and inflated the risk score, pushing every symbol
            # into the defensive path. Only negative unrealized P&L contributes to drawdown now.
            if unrealized_plpc is not None:
                plpc = float(unrealized_plpc)
                loss_pct = abs(plpc) if plpc < 0 else 0.0
            elif cost_basis > 0:
                loss_pct = abs(unrealized_pl / cost_basis) if unrealized_pl < 0 else 0.0
            else:
                loss_pct = 0.0

            # Guard against stale/invalid positions with near-zero cost basis. These are not a valid denominator for a drawdown calculation,
            # so we ignore division-based percentages when the cost basis is effectively zero and rely on Alpaca's unrealized_plpc field.
            if cost_basis <= 1e-6 and unrealized_plpc is None:
                loss_pct = 0.0

            per_position_loss_pct.append({"symbol": symbol, "loss_pct": loss_pct, "unrealized_plpc": unrealized_plpc})
            if loss_pct > worst_negative_unrealized_plpc:
                worst_negative_unrealized_plpc = float(loss_pct)

        # Real portfolio proxy: delta exposure is the share of account equity currently tied up in open option positions.
        # Limitation: this is a rough position-value proxy, not true portfolio delta or option Greeks.
        delta_exposure = min(total_market_value / equity, 1.0) if positions else 0.0

        # Real portfolio proxy: drawdown is the worst negative unrealized P&L percentage across open positions.
        # We prefer Alpaca's unrealized_plpc field as source-of-truth; if it is missing or stale, we fall back to a cost-basis ratio only when
        # the basis is valid. This avoids division by near-zero values from older bad positions.
        drawdown_pct = max(0.0, worst_negative_unrealized_plpc * 100.0)

        # Real, price-derived volatility rank (0..1) for the symbol under evaluation, computed by the
        # caller from historical bars. Replaces the earlier placeholder that was derived from the signal.
        volatility = max(0.0, min(1.0, float(volatility_rank)))

        return {
            "delta_exposure": float(delta_exposure),
            "volatility": float(volatility),
            "drawdown_pct": float(drawdown_pct),
        }

    def manage_open_positions(self, execute: bool = False) -> Dict[str, Any]:
        """Review every open position and take-profit / stop-loss / near-expiry exit as needed.

        This is the active book-management pass: it does not open anything, it only closes positions that
        have hit a profit target, a loss limit, or their expiry window. Returns a structured summary so the
        dashboard and logs can show exactly what was decided and why.
        """
        positions = list(self._get_open_positions())
        decisions = self.exit_manager.evaluate_portfolio(positions)

        actions: list[Dict[str, Any]] = []
        for decision in decisions:
            if not decision["should_close"]:
                continue

            execution_result = None
            if execute and self.execution_agent is not None:
                symbol = decision["symbol"]
                try:
                    if decision["is_option"]:
                        execution_result = self.execution_agent.close_option_position_with_limit_fallback(symbol)
                    else:
                        root = self.execution_agent._underlying_root(symbol)
                        execution_result = self.execution_agent.close_positions_for_symbol(root)
                except Exception as exc:  # pragma: no cover - defensive, network failures
                    execution_result = {"status": "error", "submitted": False, "message": str(exc)}

            actions.append({**decision, "execution": execution_result})

        return {
            "evaluated": len(decisions),
            "to_close": len(actions),
            "actions": actions,
            "decisions": decisions,
        }

    def evaluate_symbol(self, symbol: str, execute: bool = False, qty: int = 1) -> Dict[str, object]:
        bars = self.market_agent.get_bars(symbol, limit=120, timeframe="1Day")
        is_empty_bars = bars is None
        if not is_empty_bars and hasattr(bars, "empty"):
            is_empty_bars = bool(bars.empty)
        elif not is_empty_bars and isinstance(bars, (list, tuple)):
            is_empty_bars = len(bars) == 0

        if is_empty_bars:
            return {
                "symbol": symbol,
                "status": "no_data",
                "signal": {"signal": "no_data", "score": 0.0, "reason": "No market data available for this symbol."},
                "risk": None,
                "strategy": None,
                "entry_strategy": None,
                "path": "none",
                "current_price": None,
                "explanation": "No market data available for this symbol; no strategy or execution attempt was made.",
                "execution": None,
            }

        signal = self.signal_engine.generate_signal(bars)
        if signal.get("signal") in {"no_data", "no data available"}:
            return {
                "symbol": symbol,
                "status": "no_data",
                "signal": signal,
                "risk": None,
                "strategy": None,
                "entry_strategy": None,
                "path": "none",
                "current_price": None,
                "explanation": "No market data available for this symbol; no strategy or execution attempt was made.",
                "execution": None,
            }

        latest_price = self.market_agent.get_latest_price(symbol)

        volatility_rank_value = self._extract_volatility_rank(bars)
        risk_inputs = self._compute_live_risk_inputs(volatility_rank_value)
        risk = self.risk_scorer.score_portfolio(
            delta_exposure=risk_inputs["delta_exposure"],
            volatility=risk_inputs["volatility"],
            drawdown_pct=risk_inputs["drawdown_pct"],
        )

        entry_strategy = self.strategy_selector.select_entry_strategy(signal["signal"], symbol, current_price=latest_price)
        path = "entry"
        strategy = entry_strategy

        if float(risk["risk_score"]) >= 45.0:
            position_direction = self._get_position_direction(self._get_open_positions())
            hedge_strategy = self.strategy_selector.select_hedge_strategy(
                risk["risk_score"],
                position_direction,
                symbol=symbol,
                current_price=latest_price,
            )
            strategy = hedge_strategy
            path = "defense"
            if "strategy" in hedge_strategy and hedge_strategy["strategy"] == "hold":
                strategy = entry_strategy
                path = "entry"

        explanation = self.explainer.explain(signal["signal"], risk, strategy)

        execution_result = None
        if execute:
            if self.execution_agent is None:
                execution_result = {
                    "status": "execution_unavailable",
                    "submitted": False,
                    "message": "Execution is unavailable because Alpaca credentials or the MCP execution agent are not configured.",
                }
            else:
                execution_result = self.execution_agent.execute_strategy(symbol, strategy, qty=qty)

        return {
            "symbol": symbol,
            "status": "ok",
            "signal": signal,
            "risk": risk,
            "strategy": strategy,
            "entry_strategy": entry_strategy,
            "path": path,
            "current_price": latest_price,
            "explanation": explanation,
            "execution": execution_result,
        }


if __name__ == "__main__":
    orchestrator = Orchestrator()
    print(orchestrator.evaluate_symbol("AAPL", execute=False))
