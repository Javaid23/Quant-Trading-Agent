from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from alpaca.data.enums import OptionsFeed
from alpaca.data.historical import OptionHistoricalDataClient
from alpaca.data.requests import OptionChainRequest
from alpaca.trading.enums import ContractType


class StrategySelector:
    """Convert a signal or risk state into an execution-friendly structure."""

    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")
        self.option_client = None
        if self.api_key and self.secret_key:
            try:
                self.option_client = OptionHistoricalDataClient(self.api_key, self.secret_key)
            except Exception:
                self.option_client = None

    def _build_fallback_option_symbol(self, symbol: str, option_type: str, strike: float | None = None) -> str:
        """Last-resort fallback only; real chain data should be preferred whenever available."""
        option_type = (option_type or "call").lower()
        symbol = (symbol or "").upper().strip()

        expiry = (date.today() + timedelta(days=21)).strftime("%y%m%d")
        strike_value = float(strike if strike is not None else 100.0)
        strike_int = int(round(strike_value * 100))
        strike_code = f"{strike_int:08d}"
        contract_type = "C" if option_type == "call" else "P"
        return f"{symbol}{expiry}{contract_type}{strike_code}"

    def _extract_contract_map(self, chain: Any) -> Dict[str, Any]:
        if isinstance(chain, dict):
            if "option_contracts" in chain and isinstance(chain["option_contracts"], dict):
                return chain["option_contracts"]
            if all(len(str(k)) >= 10 for k in chain.keys()):
                return chain
            option_contracts = chain.get("option_contracts")
            if isinstance(option_contracts, dict):
                return option_contracts
            if isinstance(option_contracts, list):
                return {str(item.get("symbol") or item.get("contract_symbol") or idx): item for idx, item in enumerate(option_contracts)}

        option_contracts = getattr(chain, "option_contracts", None)
        if isinstance(option_contracts, dict):
            return option_contracts
        if isinstance(option_contracts, list):
            return {str(item.get("symbol") or item.get("contract_symbol") or idx): item for idx, item in enumerate(option_contracts)}

        return {}

    @staticmethod
    def _parse_option_symbol_details(symbol: str) -> tuple[str, date, float]:
        option_symbol = (symbol or "").upper().strip()
        if len(option_symbol) < 19:
            raise ValueError(f"Unsupported option symbol format: {symbol}")

        call_put = option_symbol[-9]
        if call_put not in {"C", "P"}:
            raise ValueError(f"Unsupported option symbol format: {symbol}")

        expiry_str = option_symbol[-15:-9]
        strike_digits = option_symbol[-8:]
        expiry_date = datetime.strptime(expiry_str, "%y%m%d").date()
        strike_price = float(int(strike_digits)) / 1000.0
        return call_put, expiry_date, strike_price

    def get_option_symbol_for_signal(self, symbol: str, option_type: str, current_price: float | None = None) -> str:
        symbol = (symbol or "").upper().strip()
        option_type = (option_type or "call").lower()
        if not symbol:
            raise ValueError("symbol is required to generate an option contract")

        if self.option_client is not None:
            try:
                request = OptionChainRequest(
                    underlying_symbol=symbol,
                    type=ContractType.CALL if option_type == "call" else ContractType.PUT,
                    feed=OptionsFeed.INDICATIVE,
                )
                chain = self.option_client.get_option_chain(request)
                contract_map = self._extract_contract_map(chain)

                if contract_map:
                    today = date.today()
                    target_expiry_days = 21
                    valid_contracts = []

                    for contract_key, contract in contract_map.items():
                        real_symbol = str(
                            getattr(contract, "symbol", None)
                            or (contract.get("symbol") if isinstance(contract, dict) else None)
                            or contract_key
                        ).upper()

                        try:
                            parsed_type, parsed_expiry, parsed_strike = self._parse_option_symbol_details(real_symbol)
                        except Exception:
                            continue

                        if parsed_type.lower() != option_type[0].lower():
                            continue

                        if parsed_expiry < today + timedelta(days=14):
                            continue

                        valid_contracts.append({
                            "symbol": real_symbol,
                            "expiration": parsed_expiry,
                            "strike_price": parsed_strike,
                        })

                    if valid_contracts:
                        price = float(current_price) if current_price is not None else 100.0
                        target_contract = min(
                            valid_contracts,
                            key=lambda item: (
                                abs((item["expiration"] - today).days - target_expiry_days),
                                abs(item["strike_price"] - price),
                            ),
                        )
                        return str(target_contract["symbol"]).upper()
            except Exception:
                pass

        base_price = float(current_price) if current_price is not None else 100.0
        return self._build_fallback_option_symbol(symbol, option_type, strike=base_price)

    def select_entry_strategy(self, signal: str, symbol: str, current_price: float | None = None) -> Dict[str, Any]:
        signal = (signal or "neutral").lower()
        if signal == "bullish":
            option_type = "call"
            strategy = "long_call"
        elif signal == "bearish":
            option_type = "put"
            strategy = "long_put"
        else:
            return {
                "symbol": symbol,
                "direction": "neutral",
                "option_type": "none",
                "strategy": "hold",
                "option_symbol": None,
            }

        option_symbol = self.get_option_symbol_for_signal(symbol, option_type, current_price=current_price)
        return {
            "symbol": symbol,
            "direction": "long" if signal == "bullish" else "short",
            "option_type": option_type,
            "strategy": strategy,
            "option_symbol": option_symbol,
        }

    def select_hedge_strategy(self, risk_score: float, position_direction: str) -> Dict[str, str]:
        risk_score = float(risk_score)
        direction = (position_direction or "neutral").lower()

        if risk_score >= 70:
            strategy = "exit"
            reason = "Risk score is too high; exiting to protect capital."
        elif risk_score >= 45:
            strategy = "protective_put" if direction == "long" else "covered_call"
            reason = "Medium risk detected; hedging exposure with a defensive option structure."
        elif risk_score >= 25:
            strategy = "collar" if direction == "long" else "covered_call"
            reason = "Moderate risk; tightening the position with a partial hedge."
        else:
            strategy = "hold"
            reason = "Risk remains within normal thresholds."

        return {
            "strategy": strategy,
            "reason": reason,
        }
