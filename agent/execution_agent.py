from __future__ import annotations

import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, OptionLegRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OptionType


load_dotenv()


class ExecutionAgent:
    """Minimal execution wrapper for paper-trading order placement."""

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

    def place_market_order(self, symbol: str, qty: int, side: str) -> Dict[str, Any]:
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
        }

    def place_option_order(self, symbol: str, qty: int, side: str, option_type: str, strike: float, expiry: str) -> Dict[str, Any]:
        request = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        request.option_type = option_type.upper()
        request.strike_price = float(strike)
        request.expiration_date = expiry
        response = self.client.submit_order(request)
        return {
            "id": getattr(response, "id", None),
            "status": getattr(response, "status", None),
            "symbol": symbol,
            "option_type": option_type,
            "qty": qty,
        }


if __name__ == "__main__":
    agent = ExecutionAgent()
    print(agent.client.get_account())
