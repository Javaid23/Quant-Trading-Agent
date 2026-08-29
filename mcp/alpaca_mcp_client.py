import os
from typing import Any, Dict

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient


load_dotenv()


class AlpacaMCPClient:
    """Minimal Alpaca paper-account client wrapper."""

    def __init__(self, api_key: str | None = None, secret_key: str | None = None):
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")

        if not self.api_key or not self.secret_key:
            raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set.")

        self.client = TradingClient(
            api_key=self.api_key,
            secret_key=self.secret_key,
            paper=True,
        )

    def get_account(self) -> Dict[str, Any]:
        account = self.client.get_account()
        return {
            "account_number": account.account_number,
            "status": account.status,
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
            "portfolio_value": float(account.portfolio_value),
            "equity": float(account.equity),
        }


if __name__ == "__main__":
    client = AlpacaMCPClient()
    print(client.get_account())
