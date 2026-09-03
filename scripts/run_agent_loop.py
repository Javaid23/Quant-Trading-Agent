"""Autonomous agent loop: monitor open positions and scan the watchlist on an interval.

Usage:
    set PYTHONPATH=.
    set LOOP_INTERVAL_SECONDS=120
    set MANAGE_EXECUTE=true      # actually place exit orders (default: false, dry-run)
    set SCAN_EXECUTE=false       # actually place entry orders (default: false)
    python scripts/run_agent_loop.py

Each cycle it (1) reviews open positions and takes profit / stops out / exits near expiry, and
(2) scans the watchlist for fresh signals. It idles while the market is closed. Ctrl+C to stop.
"""

from __future__ import annotations

import json
import os
import time

from agent.orchestrator import Orchestrator

WATCHLIST = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "SPY"]
INTERVAL = int(os.getenv("LOOP_INTERVAL_SECONDS", "120"))
MANAGE_EXECUTE = os.getenv("MANAGE_EXECUTE", "false").lower() in {"1", "true", "yes"}
SCAN_EXECUTE = os.getenv("SCAN_EXECUTE", "false").lower() in {"1", "true", "yes"}


def _market_open(orchestrator: Orchestrator) -> bool:
    if orchestrator.execution_agent is None:
        return False
    try:
        return bool(orchestrator.execution_agent.get_market_clock().get("is_open"))
    except Exception:
        return False


def main() -> int:
    orchestrator = Orchestrator()
    print(
        f"Autonomous loop starting: interval={INTERVAL}s manage_execute={MANAGE_EXECUTE} "
        f"scan_execute={SCAN_EXECUTE} watchlist={WATCHLIST}"
    )

    while True:
        if not _market_open(orchestrator):
            print("Market closed; idling this cycle.")
        else:
            summary = orchestrator.run_cycle(
                watchlist=WATCHLIST,
                manage=True,
                manage_execute=MANAGE_EXECUTE,
                scan=True,
                scan_execute=SCAN_EXECUTE,
            )
            managed = summary.get("managed") or {}
            closed = managed.get("to_close", 0)
            print(f"cycle: managed {managed.get('evaluated', 0)} positions, closing {closed}")
            for action in managed.get("actions", []):
                print(f"  EXIT {action['symbol']}: {action['action']} - {action['reason']}")
            for result in summary.get("scanned", []):
                if isinstance(result, dict) and result.get("status") == "ok":
                    print(
                        f"  SCAN {result['symbol']}: signal={result['signal']['signal']} "
                        f"path={result['path']} strategy={result['strategy'].get('strategy')}"
                    )

        time.sleep(INTERVAL)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nStopped.")
