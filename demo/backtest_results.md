# Indicator Combination Backtest

We tested **all 15 combinations** of our four indicators (RSI, MACD, Bollinger Bands, moving-average crossover) on **10 tickers** using the most recent ~250 daily bars each. Each combination trades the same directional model the live agent uses (long on bullish, short on bearish, flat on neutral).

**Best combination: `rsi+bollinger`** — average return 5.01% per ticker, average win rate 34.5%, 331 trades across the basket.

Tickers: AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, SPY, QQQ, NFLX

| Rank | Combination | Avg return % | Avg win rate | Trades |
| ---: | --- | ---: | ---: | ---: |
| 1 | `rsi+bollinger` | 5.01 | 34.5% | 331 |
| 2 | `bollinger` | 4.49 | 29.6% | 264 |
| 3 | `macd+bollinger` | 4.49 | 29.6% | 264 |
| 4 | `rsi+bollinger+ma` | 4.28 | 38.4% | 366 |
| 5 | `bollinger+ma` | 3.92 | 38.5% | 349 |
| 6 | `ma` | 1.7 | 42.3% | 473 |
| 7 | `macd+bollinger+ma` | 0.43 | 32.7% | 270 |
| 8 | `rsi+ma` | -0.01 | 42.9% | 508 |
| 9 | `rsi+macd+bollinger+ma` | -0.45 | 32.1% | 282 |
| 10 | `rsi` | -0.98 | 65.6% | 70 |
| 11 | `rsi+macd+bollinger` | -1.24 | 35.1% | 278 |
| 12 | `macd+ma` | -3.48 | 39.1% | 320 |
| 13 | `rsi+macd+ma` | -5.12 | 42.0% | 363 |
| 14 | `rsi+macd` | -6.53 | 44.1% | 298 |
| 15 | `macd` | -8.34 | 34.7% | 184 |

_Return is measured on the underlying directional move (the indicator edge), not option premium P&L, so combinations are compared on signal quality alone. Results depend on the sample window and are for research/paper-trading purposes only._
