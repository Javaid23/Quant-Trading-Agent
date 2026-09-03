"""Backtest every indicator combination across the watchlist and document the winner.

Usage:
    set PYTHONPATH=.
    python scripts/run_backtest_selection.py

Pulls real daily bars from Alpaca for a basket of liquid tickers, runs all 15 indicator
combinations through the ComboBacktester, prints a ranked table, and writes the results to
demo/backtest_results.md so the pitch deck can cite concrete numbers.
"""

from __future__ import annotations

import os
from pathlib import Path

from agent.entry.combo_backtester import ComboBacktester
from agent.entry.market_data_agent import MarketDataAgent

SYMBOLS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "SPY", "QQQ", "NFLX"]
LOOKBACK_BARS = int(os.getenv("BACKTEST_BARS", "250"))


def build_price_map(symbols: list[str]) -> dict[str, list[float]]:
    agent = MarketDataAgent()
    price_map: dict[str, list[float]] = {}
    for symbol in symbols:
        try:
            bars = agent.get_bars(symbol, limit=LOOKBACK_BARS, timeframe="1Day")
            if bars is not None and not bars.empty and "close" in bars.columns:
                closes = bars["close"].astype(float).tolist()
                if len(closes) > 30:
                    price_map[symbol] = closes
                    print(f"  loaded {symbol}: {len(closes)} bars")
                else:
                    print(f"  skipped {symbol}: only {len(closes)} bars")
            else:
                print(f"  skipped {symbol}: no data")
        except Exception as exc:  # noqa: BLE001
            print(f"  skipped {symbol}: {exc}")
    return price_map


def write_report(results: list[dict], symbols: list[str], bars: int) -> Path:
    report_path = Path(__file__).resolve().parents[1] / "demo" / "backtest_results.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    winner = results[0] if results else None
    lines: list[str] = []
    lines.append("# Indicator Combination Backtest")
    lines.append("")
    lines.append(
        f"We tested **all {len(results)} combinations** of our four indicators "
        "(RSI, MACD, Bollinger Bands, moving-average crossover) on **"
        f"{len(symbols)} tickers** using the most recent ~{bars} daily bars each. "
        "Each combination trades the same directional model the live agent uses "
        "(long on bullish, short on bearish, flat on neutral)."
    )
    lines.append("")
    if winner:
        lines.append(
            f"**Best combination: `{winner['combo']}`** — "
            f"average return {winner['avg_return_pct']}% per ticker, "
            f"average win rate {winner['avg_win_rate'] * 100:.1f}%, "
            f"{winner['total_trades']} trades across the basket."
        )
        lines.append("")
    lines.append(f"Tickers: {', '.join(symbols)}")
    lines.append("")
    lines.append("| Rank | Combination | Avg return % | Avg win rate | Trades |")
    lines.append("| ---: | --- | ---: | ---: | ---: |")
    for rank, row in enumerate(results, start=1):
        lines.append(
            f"| {rank} | `{row['combo']}` | {row['avg_return_pct']} | "
            f"{row['avg_win_rate'] * 100:.1f}% | {row['total_trades']} |"
        )
    lines.append("")
    lines.append(
        "_Return is measured on the underlying directional move (the indicator edge), not option "
        "premium P&L, so combinations are compared on signal quality alone. Results depend on the "
        "sample window and are for research/paper-trading purposes only._"
    )
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> int:
    print(f"Loading up to {LOOKBACK_BARS} daily bars for {len(SYMBOLS)} tickers...")
    price_map = build_price_map(SYMBOLS)
    if not price_map:
        print("No price data available; aborting.")
        return 1

    results = ComboBacktester().run_selection(price_map)

    print("\nRanked indicator combinations (best first):")
    print(f"{'Rank':>4}  {'Combination':<28}  {'AvgRet%':>8}  {'WinRate':>8}  {'Trades':>6}")
    for rank, row in enumerate(results, start=1):
        print(
            f"{rank:>4}  {row['combo']:<28}  {row['avg_return_pct']:>8}  "
            f"{row['avg_win_rate'] * 100:>7.1f}%  {row['total_trades']:>6}"
        )

    report_path = write_report(results, list(price_map.keys()), LOOKBACK_BARS)
    print(f"\nWrote report to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
