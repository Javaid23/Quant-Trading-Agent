from __future__ import annotations

import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from alpaca.data.historical import OptionHistoricalDataClient
from alpaca.data.requests import OptionLatestTradeRequest, OptionLatestQuoteRequest

from alpaca_mcp_wrapper.alpaca_mcp_client import AlpacaMCPClient


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

        self.client = AlpacaMCPClient(api_key=self.api_key, secret_key=self.secret_key)

    @staticmethod
    def _infer_option_type(option_symbol: str) -> str | None:
        option_symbol = (option_symbol or "").upper().strip()
        if len(option_symbol) < 10:
            return None
        call_put = option_symbol[-9]
        if call_put == "C":
            return "call"
        if call_put == "P":
            return "put"
        return None

    def get_market_clock(self) -> Dict[str, Any]:
        clock = self.client.get_clock()
        if isinstance(clock, dict):
            next_open = clock.get("next_open")
            next_close = clock.get("next_close")
            is_open = bool(clock.get("is_open", False))
        else:
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
        if isinstance(account, dict):
            return {
                "account_number": account.get("account_number"),
                "status": account.get("status"),
                "cash": float(account.get("cash", 0.0) or 0.0),
                "buying_power": float(account.get("buying_power", 0.0) or 0.0),
                "portfolio_value": float(account.get("portfolio_value", 0.0) or 0.0),
                "equity": float(account.get("equity", 0.0) or 0.0),
            }
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

        response = self.client.place_stock_order(symbol=symbol, side=side, qty=qty, type="market", time_in_force="day")
        return {
            "id": response.get("id") if isinstance(response, dict) else getattr(response, "id", None),
            "status": response.get("status") if isinstance(response, dict) else getattr(response, "status", None),
            "symbol": response.get("symbol") if isinstance(response, dict) else getattr(response, "symbol", None),
            "side": response.get("side") if isinstance(response, dict) else getattr(response, "side", None),
            "qty": response.get("qty") if isinstance(response, dict) else getattr(response, "qty", None),
            "order_type": "market",
        }

    def _get_option_last_price(self, symbol: str) -> float | None:
        symbol = (symbol or "").upper().strip()
        if not symbol:
            return None

        try:
            option_client = OptionHistoricalDataClient(self.api_key, self.secret_key)
            trade_req = OptionLatestTradeRequest(symbol_or_symbols=symbol)
            trade_resp = option_client.get_option_latest_trade(trade_req)
            trade = trade_resp.get(symbol)
            if trade is not None:
                trade_price = getattr(trade, "p", None)
                if trade_price is not None:
                    return float(trade_price)

            quote_req = OptionLatestQuoteRequest(symbol_or_symbols=symbol)
            quote_resp = option_client.get_option_latest_quote(quote_req)
            quote = quote_resp.get(symbol)
            if quote is not None:
                bid = getattr(quote, "bp", None)
                ask = getattr(quote, "ap", None)
                if bid is not None and ask is not None:
                    return float((float(bid) + float(ask)) / 2.0)
                if bid is not None:
                    return float(bid)
                if ask is not None:
                    return float(ask)
        except Exception:
            pass
        return None

    def close_option_position_with_limit_fallback(self, option_symbol: str, qty: int = 1) -> Dict[str, Any]:
        option_symbol = (option_symbol or "").upper().strip()
        qty = int(qty)
        if not option_symbol:
            raise ValueError("option_symbol is required")
        if qty <= 0:
            raise ValueError("qty must be greater than 0")

        try:
            market_close = self.client.close_position(option_symbol)
            result = {
                "symbol": option_symbol,
                "qty": qty,
                "order_type": "sell_to_close_market",
                "status": getattr(market_close, "status", None),
                "id": getattr(market_close, "id", None),
                "submitted": True,
                "retry_used": False,
            }
            if getattr(market_close, "status", None) is not None:
                return result
        except Exception as exc:
            market_close = None
            failure_text = str(exc).lower()
            if "no available quote" not in failure_text and "quote" not in failure_text:
                raise

        last_price = self._get_option_last_price(option_symbol)
        fallback_price = last_price if last_price is not None else 0.01
        fallback_reason = (
            "Market sell-to-close rejected because the option had no available quote; "
            "retrying with a limit order at the last known price."
            if last_price is not None else
            "Market sell-to-close rejected because the option had no available quote; "
            "retrying with a limit order at $0.01 because no last price is available."
        )

        response = self.client.place_option_order(
            option_symbol=option_symbol,
            qty=qty,
            side="sell",
            option_type=self._infer_option_type(option_symbol),
            type="limit",
            time_in_force="day",
            position_intent="sell_to_close",
            limit_price=fallback_price,
        )
        return {
            "symbol": option_symbol,
            "qty": qty,
            "order_type": "sell_to_close_limit",
            "status": response.get("status") if isinstance(response, dict) else getattr(response, "status", None),
            "id": response.get("id") if isinstance(response, dict) else getattr(response, "id", None),
            "submitted": True,
            "retry_used": True,
            "retry_reason": fallback_reason,
            "fallback_limit_price": fallback_price,
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

        response = self.client.place_option_order(
            option_symbol=option_symbol,
            qty=qty,
            side=side,
            option_type=(option_type or self._infer_option_type(option_symbol) or "unknown"),
        )
        return {
            "id": response.get("id") if isinstance(response, dict) else getattr(response, "id", None),
            "status": response.get("status") if isinstance(response, dict) else getattr(response, "status", None),
            "symbol": response.get("symbol") if isinstance(response, dict) else getattr(response, "symbol", None),
            "side": response.get("side") if isinstance(response, dict) else getattr(response, "side", None),
            "qty": response.get("qty") if isinstance(response, dict) else getattr(response, "qty", None),
            "order_type": "option_market",
            "option_type": (option_type or "unknown").upper(),
        }

    def execute_strategy(self, symbol: str, strategy: Dict[str, Any], qty: int = 1) -> Dict[str, Any]:
        strategy_name = str(strategy.get("strategy", "hold")).lower()
        option_type = str(strategy.get("option_type", "none")).lower()
        symbol = (symbol or "").upper().strip()

        if strategy_name == "hold":
            return {"message": "No order placed because strategy is hold.", "status": "skipped"}

        if strategy_name == "exit":
            option_symbol = strategy.get("option_symbol")
            if option_symbol:
                return self.close_option_position_with_limit_fallback(str(option_symbol), qty=qty)
            side = "sell"
            return self.place_market_order(symbol=symbol, qty=qty, side=side)

        if option_type in {"call", "put"}:
            option_symbol = strategy.get("option_symbol")
            if not option_symbol:
                raise ValueError("Option strategy is missing a valid OCC option symbol for Alpaca submission.")

            if strategy_name in {"long_call", "long_put", "protective_put"}:
                side = "buy"
            elif strategy_name in {"covered_call", "short_call", "short_put"}:
                side = "sell"
            else:
                side = "buy"

            return self.place_option_order(
                option_symbol=str(option_symbol),
                qty=qty,
                side=side,
                option_type=option_type.upper(),
            )

        side = "buy" if strategy_name in {"long", "buy"} else "sell"
        return self.place_market_order(symbol=symbol, qty=qty, side=side)


if __name__ == "__main__":
    agent = ExecutionAgent()
    print(agent.get_account_summary())
