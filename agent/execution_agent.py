from __future__ import annotations

import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce


load_dotenv()


class ExecutionAgent:
    """Paper-trading execution wrapper with safe validation and opt-in order placement."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        paper: bool = True,
    ):
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")
        if not self.api_key or not self.secret_key:
            raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set.")

        self.client = TradingClient(self.api_key, self.secret_key, paper=paper)

    def get_market_clock(self) -> Dict[str, Any]:
        clock = self.client.get_clock()
        next_open = getattr(clock, "next_open", None)
        next_close = getattr(clock, "next_close", None)
        is_open = bool(getattr(clock, "is_open", False))
        return {
            "is_open": is_open,
            "market_status": "open" if is_open else "closed",
            "next_open": str(next_open) if next_open is not None else None,
            "next_close": str(next_close) if next_close is not None else None,
        }

    def _market_closed_response(self, order_type: str, next_open: Optional[str] = None) -> Dict[str, Any]:
        next_open_value = next_open or "unknown"
        message = f"Markets are currently closed. Next open: {next_open_value}"
        return {
            "status": "not_submitted",
            "market_status": "closed",
            "submitted": False,
            "order_type": order_type,
            "message": message,
            "next_open": next_open_value,
        }

    def get_account_summary(self) -> Dict[str, Any]:
        account = self.client.get_account()
        return {
            "account_number": getattr(account, "account_number", None),
            "status": getattr(account, "status", None),
            "cash": float(getattr(account, "cash", 0.0)),
            "buying_power": float(getattr(account, "buying_power", 0.0)),
            "portfolio_value": float(getattr(account, "portfolio_value", 0.0)),
            "equity": float(getattr(account, "equity", 0.0)),
        }

    def place_market_order(self, symbol: str, qty: int, side: str) -> Dict[str, Any]:
        symbol = (symbol or "").upper().strip()
        qty = int(qty)
        if not symbol:
            raise ValueError("symbol is required")
        if qty <= 0:
            raise ValueError("qty must be greater than 0")

        clock = self.get_market_clock()
        if not clock["is_open"]:
            return self._market_closed_response("market", clock.get("next_open"))

        order = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        response = self.client.submit_order(order)
        return {
            "id": getattr(response, "id", None),
            "status": getattr(response, "status", None),
            "symbol": getattr(response, "symbol", None),
            "side": getattr(response, "side", None),
            "qty": getattr(response, "qty", None),
            "order_type": "market",
        }

    def place_option_order(
        self,
        option_symbol: str,
        qty: int,
        side: str,
        option_type: str | None = None,
    ) -> Dict[str, Any]:
        option_symbol = (option_symbol or "").upper().strip()
        qty = int(qty)
        if not option_symbol:
            raise ValueError("option_symbol is required")
        if qty <= 0:
            raise ValueError("qty must be greater than 0")

        clock = self.get_market_clock()
        if not clock["is_open"]:
            return self._market_closed_response("option_market", clock.get("next_open"))

        order = MarketOrderRequest(
            symbol=option_symbol,
            qty=qty,
            side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        response = self.client.submit_order(order)
        return {
            "id": getattr(response, "id", None),
            "status": getattr(response, "status", None),
            "symbol": getattr(response, "symbol", None),
            "side": getattr(response, "side", None),
            "qty": getattr(response, "qty", None),
            "order_type": "option_market",
            "option_type": (option_type or "unknown").upper(),
        }

    def execute_strategy(self, symbol: str, strategy: Dict[str, Any], qty: int = 1) -> Dict[str, Any]:
        strategy_name = str(strategy.get("strategy", "hold")).lower()
        option_type = str(strategy.get("option_type", "none")).lower()
        symbol = (symbol or "").upper().strip()

        if strategy_name == "hold":
            return {"message": "No order placed because strategy is hold.", "status": "skipped"}

        if option_type in {"call", "put"}:
            option_symbol = strategy.get("option_symbol")
            if not option_symbol:
                raise ValueError("Option strategy is missing a valid OCC option symbol for Alpaca submission.")
            return self.place_option_order(
                option_symbol=str(option_symbol),
                qty=qty,
                side="buy" if strategy_name in {"long_call", "long_put"} else "sell",
                option_type=option_type.upper(),
            )

        side = "buy" if strategy_name in {"long", "buy"} else "sell"
        return self.place_market_order(symbol=symbol, qty=qty, side=side)


if __name__ == "__main__":
    agent = ExecutionAgent()
    print(agent.get_account_summary())
