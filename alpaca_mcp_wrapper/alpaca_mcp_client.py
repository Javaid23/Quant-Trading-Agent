import asyncio
import os
import shutil
import sys
import threading
from typing import Any, Dict, List

from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StdioTransport


load_dotenv()


class AlpacaMCPClient:
    """Reusable FastMCP client wrapper around the official Alpaca MCP server.

    Performance: the MCP server is spoken to over one persistent connection kept alive on a dedicated
    background event loop, so tool calls reuse the same server subprocess instead of cold-starting a new
    one each call (which was the dominant latency). The connection lazily reconnects if it drops.
    """

    def __init__(self, api_key: str | None = None, secret_key: str | None = None):
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")

        if not self.api_key or not self.secret_key:
            raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set.")

        self.client = self
        self._server_command = self._resolve_server_command()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._mcp_client: Client | None = None
        self._connect_lock: asyncio.Lock | None = None

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is not None and self._loop.is_running():
            return self._loop
        # A ProactorEventLoop is required on Windows to spawn the stdio subprocess.
        if sys.platform == "win32" and hasattr(asyncio, "ProactorEventLoop"):
            self._loop = asyncio.ProactorEventLoop()
        else:
            self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._loop.run_forever, daemon=True, name="alpaca-mcp-loop")
        self._loop_thread.start()
        return self._loop

    def _submit(self, coro: Any) -> Any:
        """Run a coroutine on the persistent background loop from a synchronous caller."""
        loop = self._ensure_loop()
        return asyncio.run_coroutine_threadsafe(coro, loop).result()

    async def _get_mcp_client(self) -> Client:
        if self._connect_lock is None:
            self._connect_lock = asyncio.Lock()
        async with self._connect_lock:
            if self._mcp_client is not None and self._mcp_client.is_connected():
                return self._mcp_client
            client = Client(transport=self._build_transport())
            await client.__aenter__()
            self._mcp_client = client
            return self._mcp_client

    async def _reset_mcp_client(self) -> None:
        if self._mcp_client is not None:
            try:
                await self._mcp_client.__aexit__(None, None, None)
            except Exception:
                pass
        self._mcp_client = None

    def close(self) -> None:
        """Tear down the persistent connection and background loop (best effort)."""
        try:
            if self._loop is not None and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(self._reset_mcp_client(), self._loop).result(timeout=5)
                self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:
            pass

    def _resolve_server_command(self) -> str:
        configured = os.getenv("ALPACA_MCP_SERVER_CMD")
        if configured:
            return configured

        command = shutil.which("alpaca-mcp-server")
        if command:
            return command

        venv_candidates = [
            os.path.join(os.getcwd(), ".venv", "Scripts", "alpaca-mcp-server.exe"),
            os.path.join(os.getcwd(), ".venv", "Scripts", "alpaca-mcp-server"),
            os.path.join(os.path.dirname(__file__), "..", ".venv", "Scripts", "alpaca-mcp-server.exe"),
            os.path.join(os.path.dirname(__file__), "..", ".venv", "Scripts", "alpaca-mcp-server"),
        ]
        for candidate in venv_candidates:
            if os.path.exists(candidate):
                return candidate

        raise FileNotFoundError(
            "alpaca-mcp-server executable not found. Install the official Alpaca MCP server or set ALPACA_MCP_SERVER_CMD."
        )

    def _build_transport(self) -> StdioTransport:
        env = {
            "ALPACA_API_KEY": self.api_key,
            "ALPACA_SECRET_KEY": self.secret_key,
            "ALPACA_PAPER_TRADE": "true",
        }
        return StdioTransport(
            command=self._server_command,
            args=["--transport", "stdio"],
            env=env,
        )

    @staticmethod
    def _unwrap_mcp_result(result: Any) -> Any:
        if hasattr(result, "data") and result.data is not None:
            payload = result.data
        elif hasattr(result, "structured_content") and result.structured_content is not None:
            payload = result.structured_content
        else:
            payload = result

        if isinstance(payload, dict) and "_alpaca_mcp_security" in payload and "data" in payload:
            return payload["data"]
        if isinstance(payload, dict) and "data" in payload and isinstance(payload["data"], (dict, list)):
            return payload["data"]
        return payload

    async def _call_tool(self, tool_name: str, params: Dict[str, Any] | None = None) -> Any:
        try:
            client = await self._get_mcp_client()
            result = await client.call_tool(tool_name, params or {})
        except Exception:
            # The persistent connection may have dropped; reconnect once and retry.
            await self._reset_mcp_client()
            client = await self._get_mcp_client()
            result = await client.call_tool(tool_name, params or {})
        return self._unwrap_mcp_result(result)

    async def aget_account(self) -> Dict[str, Any]:
        payload = await self._call_tool("get_account_info", {})
        if not isinstance(payload, dict):
            return {}
        return {
            "account_number": payload.get("account_number"),
            "status": payload.get("status"),
            "cash": float(payload.get("cash", 0.0) or 0.0),
            "buying_power": float(payload.get("buying_power", 0.0) or 0.0),
            "portfolio_value": float(payload.get("portfolio_value", 0.0) or 0.0),
            "equity": float(payload.get("equity", 0.0) or 0.0),
        }

    def get_account(self) -> Dict[str, Any]:
        return self._submit(self.aget_account())

    async def aget_clock(self) -> Dict[str, Any]:
        payload = await self._call_tool("get_clock", {})
        if not isinstance(payload, dict):
            return {"is_open": False, "market_status": "closed", "next_open": None, "next_close": None}
        return {
            "is_open": bool(payload.get("is_open", False)),
            "market_status": "open" if bool(payload.get("is_open", False)) else "closed",
            "next_open": payload.get("next_open"),
            "next_close": payload.get("next_close"),
        }

    def get_clock(self) -> Dict[str, Any]:
        return self._submit(self.aget_clock())

    async def aget_all_positions(self) -> List[Dict[str, Any]]:
        payload = await self._call_tool("get_all_positions", {})
        if isinstance(payload, dict):
            payload = payload.get("result", [])
        if not isinstance(payload, list):
            return []
        return [dict(position) if isinstance(position, dict) else position for position in payload]

    def get_all_positions(self) -> List[Dict[str, Any]]:
        return self._submit(self.aget_all_positions())

    async def aplace_option_order(
        self,
        option_symbol: str,
        qty: int,
        side: str,
        type: str = "market",
        time_in_force: str = "day",
        position_intent: str | None = None,
        limit_price: float | str | None = None,
        client_order_id: str | None = None,
        option_type: str | None = None,
    ) -> Dict[str, Any]:
        option_symbol = (option_symbol or "").upper().strip()
        if not option_symbol:
            raise ValueError("option_symbol is required")

        order_body: Dict[str, Any] = {
            "symbol": option_symbol,
            "qty": str(int(qty)),
            "side": str(side).lower(),
            "type": type,
            "time_in_force": time_in_force,
        }
        if position_intent is not None:
            order_body["position_intent"] = position_intent
        if limit_price is not None:
            order_body["limit_price"] = str(limit_price)
        if client_order_id is not None:
            order_body["client_order_id"] = client_order_id
        # NOTE: the Alpaca MCP server's place_option_order tool does not accept an `option_type`
        # argument and rejects the whole order if one is sent. The call/put is already encoded in the
        # OCC `symbol`, so we deliberately accept the parameter for caller convenience but never forward
        # it to the tool.

        return await self._call_tool("place_option_order", order_body)

    def place_option_order(
        self,
        option_symbol: str,
        qty: int,
        side: str,
        option_type: str | None = None,
        type: str = "market",
        time_in_force: str = "day",
        position_intent: str | None = None,
        limit_price: float | str | None = None,
        client_order_id: str | None = None,
    ) -> Dict[str, Any]:
        return self._submit(
            self.aplace_option_order(
                option_symbol=option_symbol,
                qty=qty,
                side=side,
                type=type,
                time_in_force=time_in_force,
                position_intent=position_intent,
                limit_price=limit_price,
                client_order_id=client_order_id,
                option_type=option_type,
            )
        )

    async def aplace_option_mleg_order(
        self,
        legs: List[Dict[str, Any]],
        qty: int = 1,
        type: str = "market",
        time_in_force: str = "day",
        limit_price: float | str | None = None,
        client_order_id: str | None = None,
    ) -> Dict[str, Any]:
        if not legs:
            raise ValueError("legs are required for a multi-leg order")
        order_body: Dict[str, Any] = {
            "qty": str(int(qty)),
            "type": type,
            "time_in_force": time_in_force,
            "order_class": "mleg",
            "legs": legs,
        }
        if limit_price is not None:
            order_body["limit_price"] = str(limit_price)
        if client_order_id is not None:
            order_body["client_order_id"] = client_order_id
        return await self._call_tool("place_option_order", order_body)

    def place_option_mleg_order(
        self,
        legs: List[Dict[str, Any]],
        qty: int = 1,
        type: str = "market",
        time_in_force: str = "day",
        limit_price: float | str | None = None,
        client_order_id: str | None = None,
    ) -> Dict[str, Any]:
        return self._submit(
            self.aplace_option_mleg_order(
                legs=legs,
                qty=qty,
                type=type,
                time_in_force=time_in_force,
                limit_price=limit_price,
                client_order_id=client_order_id,
            )
        )

    async def aclose_position(self, symbol_or_asset_id: str, qty: str | int | None = None, percentage: str | int | None = None) -> Dict[str, Any]:
        payload = {"symbol_or_asset_id": symbol_or_asset_id}
        if qty is not None:
            payload["qty"] = str(qty)
        if percentage is not None:
            payload["percentage"] = str(percentage)
        return await self._call_tool("close_position", payload)

    def close_position(self, symbol_or_asset_id: str, qty: str | int | None = None, percentage: str | int | None = None) -> Dict[str, Any]:
        return self._submit(self.aclose_position(symbol_or_asset_id, qty=qty, percentage=percentage))

    async def aplace_stock_order(self, symbol: str, side: str, qty: int | str, type: str = "market", time_in_force: str = "day") -> Dict[str, Any]:
        payload = {
            "symbol": symbol.upper(),
            "side": str(side).lower(),
            "qty": str(qty),
            "type": type,
            "time_in_force": time_in_force,
        }
        return await self._call_tool("place_stock_order", payload)

    def place_stock_order(self, symbol: str, side: str, qty: int | str, type: str = "market", time_in_force: str = "day") -> Dict[str, Any]:
        return self._submit(self.aplace_stock_order(symbol=symbol, side=side, qty=qty, type=type, time_in_force=time_in_force))


if __name__ == "__main__":
    client = AlpacaMCPClient()
    print(client.get_account())
