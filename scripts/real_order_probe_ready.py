"""Ready-to-run live paper-order probe for the next market open.

Usage examples:
    set PYTHONPATH=.
    set PROBE_SYMBOL=AAPL
    set PROBE_QTY=1
    python scripts/real_order_probe_ready.py

This script is intentionally verbose and prints:
- the MCP-based market clock result first
- the exact MCP tool call name and parameters used
- the evaluate_symbol(..., execute=True, qty=...) result
- the returned order metadata
- the MCP positions snapshot immediately afterward

It will exit without placing an order if the market is closed.
"""

from __future__ import annotations

import asyncio
import os
import sys
from contextlib import suppress
from typing import Any, Callable, Dict

from agent.orchestrator import Orchestrator
from alpaca_mcp_wrapper.alpaca_mcp_client import AlpacaMCPClient


PROBE_SYMBOL = os.getenv("PROBE_SYMBOL", "AAPL").upper().strip()
PROBE_QTY = int(os.getenv("PROBE_QTY", "1"))
POST_ORDER_POSITION_POLL_COUNT = int(os.getenv("PROBE_POSITION_POLLS", "3"))
POST_ORDER_POSITION_POLL_SECONDS = float(os.getenv("PROBE_POSITION_POLL_SECONDS", "2"))


_original_call_tool = AlpacaMCPClient._call_tool


async def _logging_call_tool(self: AlpacaMCPClient, tool_name: str, params: Dict[str, Any] | None = None) -> Any:
    params = params or {}
    print(
        f"[MCP PROBE] invoking tool={tool_name} params={params} "
        f"transport=FastMCP Client/StdioTransport"
    )
    result = await _original_call_tool(self, tool_name, params)
    print(f"[MCP PROBE] tool={tool_name} response={result}")
    return result


def _patch_mcp_call_logging() -> None:
    AlpacaMCPClient._call_tool = _logging_call_tool  # type: ignore[assignment]


def _restore_mcp_call_logging() -> None:
    AlpacaMCPClient._call_tool = _original_call_tool  # type: ignore[assignment]


def _normalize_positions(raw_positions: Any) -> list[dict[str, Any]]:
    if raw_positions is None:
        return []
    if isinstance(raw_positions, dict):
        if isinstance(raw_positions.get("result"), list):
            raw_positions = raw_positions["result"]
        elif isinstance(raw_positions.get("data"), list):
            raw_positions = raw_positions["data"]
        else:
            raw_positions = [raw_positions]
    if not isinstance(raw_positions, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in raw_positions:
        if isinstance(item, dict):
            normalized.append(item)
        else:
            normalized.append({"raw": item})
    return normalized


def _matches_symbol(position: dict[str, Any], symbol: str) -> bool:
    pos_symbol = str(position.get("symbol", "") or "").upper().strip()
    if pos_symbol == symbol:
        return True
    asset_id = str(position.get("asset_id", "") or "").upper().strip()
    return asset_id == symbol


def main() -> int:
    _patch_mcp_call_logging()
    orchestrator = Orchestrator()

    try:
        if orchestrator.execution_agent is None:
            print("[PROBE] ExecutionAgent could not be initialized; missing Alpaca credentials?")
            return 2

        print(f"[PROBE] target_symbol={PROBE_SYMBOL} qty={PROBE_QTY}")

        clock = orchestrator.execution_agent.get_market_clock()
        print(f"[PROBE] market_clock={clock}")
        if not clock.get("is_open"):
            print("[PROBE] Market is closed. Exiting without placing an order.")
            return 0

        result = orchestrator.evaluate_symbol(PROBE_SYMBOL, execute=True, qty=PROBE_QTY)
        print(f"[PROBE] evaluate_symbol_result={result}")

        execution = result.get("execution") or {}
        order_id = execution.get("id")
        order_status = execution.get("status")
        order_symbol = execution.get("symbol")
        print(
            f"[PROBE] order_summary id={order_id} status={order_status} symbol={order_symbol}"
        )

        if not order_symbol:
            print("[PROBE] No order symbol returned; cannot verify positions.")
            return 1

        print("[PROBE] fetching positions via MCP to confirm visibility...")
        matched_positions: list[dict[str, Any]] = []
        for attempt in range(1, POST_ORDER_POSITION_POLL_COUNT + 1):
            positions_raw = orchestrator.execution_agent.client.get_all_positions()
            positions = _normalize_positions(positions_raw)
            matched_positions = [pos for pos in positions if _matches_symbol(pos, str(order_symbol))]
            print(
                f"[PROBE] positions_attempt={attempt} total_positions={len(positions)} "
                f"matched_positions={matched_positions}"
            )
            if matched_positions:
                break
            if attempt < POST_ORDER_POSITION_POLL_COUNT:
                asyncio.run(asyncio.sleep(POST_ORDER_POSITION_POLL_SECONDS))

        if matched_positions:
            print("[PROBE] position visibility confirmed from MCP side.")
        else:
            print(
                "[PROBE] no matching position was visible yet via MCP. "
                "The order may still be pending fill, so check the paper dashboard too."
            )

        return 0
    finally:
        _restore_mcp_call_logging()


if __name__ == "__main__":
    raise SystemExit(main())
