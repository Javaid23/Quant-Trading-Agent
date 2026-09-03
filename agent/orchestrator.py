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
        except Exception:
            # Missing credentials (ValueError) or a missing MCP server binary (FileNotFoundError, e.g. on a
            # cloud host without the submodule). Degrade gracefully; market data and analytics still work.
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

    @staticmethod
    def _filter_positions_for_symbol(positions: Iterable[Any], symbol: str) -> list:
        """Return only the positions (stock or option) whose underlying is `symbol`."""
        symbol = (symbol or "").upper().strip()
        matched = []
        for position in positions:
            position_symbol = position.get("symbol") if isinstance(position, dict) else getattr(position, "symbol", None)
            if position_symbol and ExecutionAgent._underlying_root(str(position_symbol)) == symbol:
                matched.append(position)
        return matched

    def _get_account_equity(self) -> float:
        equity = 0.0
        if self.execution_agent is not None and self.execution_agent.client is not None:
            try:
                account = self.execution_agent.client.get_account()
                equity = float(getattr(account, "equity", 0.0) or 0.0)
            except Exception:
                equity = 0.0
        return equity if equity > 0 else 1.0

    def _compute_live_risk_inputs(self, volatility_rank: float) -> Dict[str, float]:
        """Portfolio-wide risk inputs across every open position."""
        positions = list(self._get_open_positions())
        equity = self._get_account_equity()
        return self._risk_inputs_from_positions(positions, equity, volatility_rank)

    def _risk_inputs_from_positions(self, positions: Iterable[Any], equity: float, volatility_rank: float) -> Dict[str, float]:
        positions = list(positions)
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

        # Capital-at-risk proxy: the share of account equity currently tied up in open positions.
        # Limitation: this is a position-value proxy, not true portfolio delta or option Greeks.
        capital_at_risk = min(total_market_value / equity, 1.0) if positions else 0.0

        # Real portfolio proxy: drawdown is the worst negative unrealized P&L percentage across open positions.
        # We prefer Alpaca's unrealized_plpc field as source-of-truth; if it is missing or stale, we fall back to a cost-basis ratio only when
        # the basis is valid. This avoids division by near-zero values from older bad positions.
        drawdown_pct = max(0.0, worst_negative_unrealized_plpc * 100.0)

        # Real, price-derived volatility rank (0..1) for the symbol under evaluation, computed by the
        # caller from historical bars. Replaces the earlier placeholder that was derived from the signal.
        volatility = max(0.0, min(1.0, float(volatility_rank)))

        return {
            "capital_at_risk": float(capital_at_risk),
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

    def run_cycle(
        self,
        watchlist: Iterable[str] | None = None,
        manage: bool = True,
        manage_execute: bool = False,
        scan: bool = True,
        scan_execute: bool = False,
        qty: int = 1,
    ) -> Dict[str, Any]:
        """Run one autonomous cycle: manage open positions, then scan the watchlist.

        Defaults are deliberately safe: the cycle actively manages existing risk (take-profit /
        stop-loss / expiry) but only *suggests* new entries unless scan_execute is turned on. This is
        the loop a scheduler calls repeatedly to make the agent autonomous rather than click-driven.
        """
        summary: Dict[str, Any] = {"managed": None, "scanned": []}

        if manage:
            summary["managed"] = self.manage_open_positions(execute=manage_execute)

        if scan and watchlist:
            for symbol in watchlist:
                try:
                    summary["scanned"].append(self.evaluate_symbol(symbol, execute=scan_execute, qty=qty))
                except Exception as exc:  # pragma: no cover - defensive, network failures
                    summary["scanned"].append({"symbol": symbol, "status": "error", "error": str(exc)})

        return summary

    def scan_watchlist(self, symbols: Iterable[str]) -> list:
        """Fast signal+risk snapshot across many symbols for the dashboard scan.

        Deliberately lightweight: it batches the price fetch into one request, fetches positions/account
        once, and skips the expensive per-symbol option-chain resolution and LLM explanation that
        evaluate_symbol does. Returns one row per symbol with signal, score, strategy name, and risk.
        """
        symbols = [str(s).upper().strip() for s in symbols if s]
        bars_by_symbol = {}
        try:
            bars_by_symbol = self.market_agent.get_bars_multi(symbols, limit=120, timeframe="1Day")
        except Exception:
            bars_by_symbol = {}

        open_positions = list(self._get_open_positions())
        equity = self._get_account_equity()

        rows = []
        for symbol in symbols:
            bars = bars_by_symbol.get(symbol)
            is_empty = bars is None or (hasattr(bars, "empty") and bool(bars.empty))
            if is_empty:
                rows.append({"symbol": symbol, "status": "no_data", "signal": "no_data", "score": None, "strategy": "hold", "risk": None, "risk_level": None})
                continue

            signal = self.signal_engine.generate_signal(bars)
            if signal.get("signal") in {"no_data", "no data available"}:
                rows.append({"symbol": symbol, "status": "no_data", "signal": "no_data", "score": None, "strategy": "hold", "risk": None, "risk_level": None})
                continue

            volatility = self._extract_volatility_rank(bars)
            symbol_positions = self._filter_positions_for_symbol(open_positions, symbol)
            inputs = self._risk_inputs_from_positions(symbol_positions, equity, volatility)
            risk = self.risk_scorer.score_portfolio(
                capital_at_risk=inputs["capital_at_risk"], volatility=inputs["volatility"], drawdown_pct=inputs["drawdown_pct"]
            )
            direction = signal["signal"]
            strategy = "long_call" if direction == "bullish" else ("long_put" if direction == "bearish" else "hold")
            rows.append({
                "symbol": symbol,
                "status": "ok",
                "signal": direction,
                "score": signal["score"],
                "strategy": strategy,
                "risk": risk["risk_score"],
                "risk_level": risk["level"],
            })
        return rows

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
        open_positions = list(self._get_open_positions())
        equity = self._get_account_equity()
        symbol_positions = self._filter_positions_for_symbol(open_positions, symbol)
        has_symbol_position = len(symbol_positions) > 0

        # The entry/defense decision for THIS symbol is driven by this symbol's own risk, not the whole
        # book, so a bullish signal on an unrelated name is never hijacked into "exit" just because other
        # positions are underwater. Portfolio-wide risk is reported separately for monitoring.
        symbol_inputs = self._risk_inputs_from_positions(symbol_positions, equity, volatility_rank_value)
        risk = self.risk_scorer.score_portfolio(
            capital_at_risk=symbol_inputs["capital_at_risk"],
            volatility=symbol_inputs["volatility"],
            drawdown_pct=symbol_inputs["drawdown_pct"],
        )
        portfolio_inputs = self._risk_inputs_from_positions(open_positions, equity, volatility_rank_value)
        portfolio_risk = self.risk_scorer.score_portfolio(
            capital_at_risk=portfolio_inputs["capital_at_risk"],
            volatility=portfolio_inputs["volatility"],
            drawdown_pct=portfolio_inputs["drawdown_pct"],
        )

        entry_strategy = self.strategy_selector.select_entry_strategy(signal["signal"], symbol, current_price=latest_price)
        path = "entry"
        strategy = entry_strategy

        # Only defend a symbol we actually hold and whose own risk is elevated; otherwise trade the signal.
        if has_symbol_position and float(risk["risk_score"]) >= 45.0:
            position_direction = self._get_position_direction(symbol_positions)
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
            "portfolio_risk": portfolio_risk,
            "has_symbol_position": has_symbol_position,
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
