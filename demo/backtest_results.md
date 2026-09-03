# Indicator Combination Backtest

We tested **all 15 combinations** of our four indicators (RSI, MACD, Bollinger Bands, moving-average crossover) on **10 tickers** using the most recent ~250 daily bars each. Each combination trades the same directional model the live agent uses (long on bullish, short on bearish, flat on neutral).

**Best combination: `bollinger`** — average return 4.45% per ticker, average win rate 29.6%, 264 trades across the basket.

Tickers: AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, SPY, QQQ, NFLX

| Rank | Combination | Avg return % | Avg win rate | Trades |
| ---: | --- | ---: | ---: | ---: |
| 1 | `bollinger` | 4.45 | 29.6% | 264 |
| 2 | `bollinger+ma` | 3.9 | 38.5% | 349 |
| 3 | `rsi+bollinger` | 3.66 | 39.2% | 398 |
| 4 | `rsi+bollinger+ma` | 2.54 | 39.2% | 401 |
| 5 | `ma` | 1.67 | 42.3% | 473 |
| 6 | `rsi+ma` | -0.03 | 42.9% | 508 |
| 7 | `rsi` | -0.98 | 65.6% | 70 |
| 8 | `rsi+macd+ma` | -5.13 | 39.6% | 316 |
| 9 | `macd+bollinger+ma` | -6.75 | 30.5% | 231 |
| 10 | `rsi+macd+bollinger+ma` | -7.85 | 31.1% | 237 |
| 11 | `macd` | -8.35 | 34.7% | 184 |
| 12 | `macd+bollinger` | -8.35 | 34.7% | 184 |
| 13 | `macd+ma` | -8.35 | 34.7% | 184 |
| 14 | `rsi+macd+bollinger` | -8.35 | 34.7% | 184 |
| 15 | `rsi+macd` | -8.73 | 39.1% | 241 |

_Return is measured on the underlying directional move (the indicator edge), not option premium P&L, so combinations are compared on signal quality alone. Results depend on the sample window and are for research/paper-trading purposes only._
