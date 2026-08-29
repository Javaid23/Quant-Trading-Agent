# CLAUDE.md

This file gives context to Claude Code (or any AI assistant) working in this repository.

## Project

**Quant Trading Agent**
Repo: git@github.com:Javaid23/Quant-Trading-Agent.git
Built for the Alpaca AI Trading Agents Hackathon (lablab.ai), 28 August – 4 September 2026.
Team: Bajwa Bulls

## What this project does

An autonomous agent with two decision modes, both executing live on an Alpaca paper trading account:

1. **Entry mode** — analyzes a small set of proven technical indicators (RSI, MACD, Bollinger Bands, moving average crossovers, IV rank) to generate a bullish/bearish/neutral signal. Backtested against historical data to find the best-performing indicator combination. When a signal fires, the agent expresses the view through an options trade (buy a call on bullish, buy a put on bearish) rather than the underlying stock.

2. **Defense mode** — continuously monitors portfolio risk (delta exposure, IV rank shifts, drawdown from recent high) once positions are open. Automatically hedges (protective put, covered call, or collar) or exits if risk crosses a threshold.

Every decision is logged with a plain-language explanation generated via an LLM call (Featherless AI), and shown live on a Streamlit dashboard.

## Hard requirements (from the hackathon)

- Must use Alpaca's Trading API, MCP server, and/or CLI
- Strategy **must incorporate options trading** (not just stocks)
- Must run on a **new, dedicated Alpaca paper trading account** created specifically for this submission, never a reused one
- Final submission needs: a working prototype deployed online, a video demo, a pitch deck, and a GitHub repo

## Architecture

```
Orchestrator (main loop)
  ├── Market Data Agent      — pulls prices, volume, options chain via Alpaca/MCP
  ├── Signal Engine          — entry mode, indicator-based bullish/bearish signal
  ├── Risk Monitor           — defense mode, portfolio risk scoring
  ├── Strategy Selector      — decides entry structure or hedge structure
  ├── Execution Agent        — places orders via Alpaca MCP tools
  ├── Explainer              — plain-language reasoning log (Featherless LLM)
  └── Dashboard              — Streamlit, shows portfolio, risk meter, decision log
```

## Complete project structure

```
Quant-Trading-Agent/
├── README.md
├── CLAUDE.md
├── .env.example
├── .gitignore
├── requirements.txt
│
├── agent/
│   ├── __init__.py
│   ├── orchestrator.py              # main loop, ties everything together
│   │
│   ├── entry/
│   │   ├── __init__.py
│   │   ├── market_data_agent.py     # pulls price bars, volume, options chain
│   │   ├── indicators.py            # RSI, MACD, Bollinger Bands, MA crossovers, IV rank
│   │   ├── backtester.py            # tests indicator combos on historical data
│   │   └── signal_engine.py         # generates bullish/bearish/neutral signal
│   │
│   ├── defense/
│   │   ├── __init__.py
│   │   ├── risk_scorer.py           # delta exposure, IV shift, drawdown → risk score
│   │   └── hedge_selector.py        # picks protective put / covered call / collar
│   │
│   ├── strategy_selector.py         # turns entry signal or risk score into a concrete options structure
│   ├── execution_agent.py           # places/rolls/closes orders via MCP tools
│   └── explainer.py                 # plain-language reasoning log via Featherless LLM
│
├── mcp/
│   ├── __init__.py
│   └── alpaca_mcp_client.py         # wraps Alpaca MCP server connection
│
├── data/
│   ├── watchlist.json               # tickers being monitored
│   └── logs/                        # decision + trade history (JSON/CSV)
│
├── dashboard/
│   ├── app.py                       # Streamlit entry point
│   └── components/
│       ├── portfolio_view.py
│       ├── risk_meter.py
│       ├── signal_panel.py
│       └── decision_log.py
│
├── tests/
│   ├── test_indicators.py
│   ├── test_risk_scorer.py
│   ├── test_signal_engine.py
│   └── test_strategy_selector.py
│
└── demo/
    └── demo_script.md               # 2-3 minute walkthrough for judges
```

## Tech stack

- Python
- Alpaca Trading API + Alpaca MCP server (paper trading only, never live)
- Featherless AI for LLM reasoning/explanation calls (not Anthropic/Claude API)
- Streamlit for the dashboard, deployed on Streamlit Community Cloud
- pandas / numpy for indicator calculations and backtesting
- Local JSON/CSV for logs, no database

## Environment variables

```
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
FEATHERLESS_API_KEY=
```

All keys live in `.env`, which is gitignored. Never hardcode keys in source files, never commit `.env`.

## Build order

1. `mcp/alpaca_mcp_client.py` + `agent/entry/market_data_agent.py` — confirm live data pull works
2. `agent/entry/indicators.py` + `agent/entry/backtester.py` — validate which indicator combination performs best historically
3. `agent/entry/signal_engine.py` — turn the winning combination into a live bullish/bearish/neutral signal
4. `agent/defense/risk_scorer.py` + `agent/defense/hedge_selector.py` — portfolio risk monitoring
5. `agent/strategy_selector.py` + `agent/execution_agent.py` — connect signals/risk to real options orders on the paper account
6. `agent/explainer.py` — plain-language decision logging
7. `agent/orchestrator.py` — tie everything into one running loop
8. `dashboard/app.py` — Streamlit UI, deploy to Streamlit Community Cloud
9. `demo/demo_script.md`, pitch deck, video

## Conventions

- Keep LLM calls (Featherless) minimal: only for the Explainer and edge-case judgment in the Strategy Selector, not for every data pull or indicator calculation. Core signal and risk logic should be deterministic Python, not LLM-driven, for reliability and to conserve API credits.
- All trading logic must target the Alpaca **paper** endpoint (`https://paper-api.alpaca.markets`). Never point at the live endpoint.
- Every trade decision (entry or hedge) must produce a corresponding log entry with a plain-language explanation before or immediately after execution.
- Prefer simple, well-known indicators over exotic ones. The differentiator is autonomy and explainability, not indicator novelty.
- Backtest results and indicator selection should be documented in `demo/` so the pitch deck can reference "we tested X combinations and found Y performed best."

## Current status

Repo initialized. Virtual environment and dependencies set up. Alpaca paper trading keys and Featherless API key configured in `.env`. Next step: build `mcp/alpaca_mcp_client.py` and `agent/entry/market_data_agent.py`, then confirm a live connection before writing indicator, signal, or execution logic.
