# Indicator Combination Backtest

We tested **all 15 combinations** of our four indicators (RSI, MACD, Bollinger Bands, moving-average crossover) on **10 tickers** using the most recent ~250 daily bars each, and validated the winner **out-of-sample** on a 70/30 chronological split (indicators warmed on the first 70%, performance measured only on the unseen last 30%). Combinations are ranked by Sharpe.

**Headline (out-of-sample): `rsi` — Sharpe 0.08, worst drawdown -6.84%, avg return 0.58% per ticker over 17 unseen-period trades.**

In-sample best: `rsi` — Sharpe 0.26, return -0.98%, win rate 65.6%.

Tickers: AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, SPY, QQQ, NFLX

## Out-of-sample (last 30%, unseen)
| Rank | Combination | Avg return % | Sharpe | Worst DD % | Win rate | Trades |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | `rsi` | 0.58 | 0.08 | -6.84 | 40.0% | 17 |
| 2 | `rsi+ma` | 4.01 | 0.05 | -41.03 | 46.9% | 168 |
| 3 | `ma` | 4.56 | 0.02 | -41.03 | 47.9% | 158 |
| 4 | `rsi+macd+ma` | 1.44 | -0.09 | -23.86 | 44.2% | 117 |
| 5 | `macd+ma` | 1.06 | -0.16 | -23.86 | 44.1% | 105 |
| 6 | `rsi+bollinger+ma` | -0.75 | -0.34 | -38.14 | 40.2% | 122 |
| 7 | `macd` | -2.07 | -0.39 | -27.09 | 40.6% | 59 |
| 8 | `bollinger+ma` | -1.69 | -0.4 | -38.14 | 38.9% | 118 |
| 9 | `rsi+macd` | -1.33 | -0.57 | -27.09 | 39.7% | 80 |
| 10 | `rsi+macd+bollinger+ma` | -4.55 | -0.76 | -30.67 | 31.4% | 102 |
| 11 | `macd+bollinger+ma` | -5.6 | -0.79 | -30.67 | 29.9% | 97 |
| 12 | `rsi+macd+bollinger` | -4.73 | -0.83 | -24.97 | 32.8% | 89 |
| 13 | `rsi+bollinger` | -7.44 | -0.87 | -36.82 | 30.3% | 121 |
| 14 | `bollinger` | -7.61 | -1.01 | -36.82 | 27.4% | 106 |
| 15 | `macd+bollinger` | -7.61 | -1.01 | -36.82 | 27.4% | 106 |

## In-sample (full window)
| Rank | Combination | Avg return % | Sharpe | Worst DD % | Win rate | Trades |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | `rsi` | -0.98 | 0.26 | -25.03 | 65.6% | 70 |
| 2 | `bollinger+ma` | 3.61 | 0.1 | -72.1 | 38.5% | 349 |
| 3 | `rsi+ma` | -0.33 | 0.09 | -110.66 | 42.9% | 508 |
| 4 | `rsi+bollinger+ma` | 3.97 | 0.08 | -72.1 | 38.4% | 366 |
| 5 | `ma` | 1.38 | 0.08 | -99.8 | 42.3% | 473 |
| 6 | `rsi+macd+ma` | -5.37 | 0.01 | -105.63 | 42.0% | 363 |
| 7 | `macd+ma` | -3.74 | -0.03 | -99.91 | 39.1% | 320 |
| 8 | `rsi+macd` | -6.73 | -0.07 | -106.07 | 44.1% | 298 |
| 9 | `rsi+macd+bollinger` | -1.5 | -0.12 | -47.97 | 35.1% | 278 |
| 10 | `macd+bollinger+ma` | 0.17 | -0.14 | -55.44 | 32.7% | 270 |
| 11 | `macd` | -8.55 | -0.14 | -117.05 | 34.7% | 184 |
| 12 | `rsi+bollinger` | 4.7 | -0.16 | -60.25 | 34.5% | 331 |
| 13 | `rsi+macd+bollinger+ma` | -0.71 | -0.22 | -55.44 | 32.1% | 282 |
| 14 | `bollinger` | 4.16 | -0.31 | -59.19 | 29.6% | 264 |
| 15 | `macd+bollinger` | 4.16 | -0.31 | -59.19 | 29.6% | 264 |

_Return is the cumulative per-trade move on the underlying (the indicator edge), not option premium P&L, so combinations are compared on signal quality alone. Sharpe is per-trade risk-adjusted return. Results depend on the sample window and are for research/paper-trading purposes only._
