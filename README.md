# Quant Trading Agent

A paper-trading options intelligence agent built for the Alpaca AI Trading Agents Hackathon.

## Overview

This project creates an autonomous trading assistant that combines:

- market data collection from Alpaca
- technical signal generation using RSI, MACD, Bollinger Bands, and moving-average logic
- portfolio risk scoring and defensive execution logic
- options-based strategy selection for bullish and bearish views
- plain-language explanations for each decision
- a professional Streamlit dashboard for live monitoring

The goal is to make a disciplined, explainable signal engine that behaves like a practical trading desk assistant rather than a black-box model.

## Why this matters

Many retail trading tools are either too opaque or too simplistic. This project focuses on three ideas:

1. Explainability — every signal and risk decision is readable in plain language.
2. Discipline — decisions are based on deterministic indicators rather than emotion or guesswork.
3. Risk control — the system includes defense logic before and after entry.

## Architecture

- Market data module: live quote and bar collection from Alpaca
- Signal engine: technical analysis and directional scoring
- Risk engine: delta, IV, and drawdown-based monitoring
- Strategy selector: maps signals to options structures
- Execution layer: paper-trading order placement
- Dashboard: live view of signals, strategy, and decision logs

## Setup

1. Clone the repository with the Alpaca MCP server included as a submodule:
   - If you are cloning for the first time:
     `git clone --recurse-submodules https://github.com/Javaid23/Quant-Trading-Agent.git`
   - If you already cloned the repo:
     `git submodule update --init --recursive`
2. Create and activate a Python virtual environment.
3. Install the main project dependencies:
   `pip install -r requirements.txt`
4. Install the Alpaca MCP server from the local submodule so the executable is available to the app:
   `pip install -e ./mcp_server`
5. Copy `.env.example` to `.env` and fill in your Alpaca paper-trading keys and Featherless key.
6. Start the Alpaca MCP server in a separate terminal:
   `alpaca-mcp-server --transport stdio`
7. Run the Streamlit app in another terminal:
   `streamlit run dashboard/app.py`
8. Analyze a ticker from the dashboard watchlist or search box.

### MCP server details

This repository keeps `mcp_server/` as a git submodule pointing to the official [`alpacahq/alpaca-mcp-server`](https://github.com/alpacahq/alpaca-mcp-server) repository. That means the app stays reproducible while still using the upstream server source directly from the checked-in submodule.

If you need to refresh the submodule later, run:

`git submodule update --init --recursive`

The MCP server exposes its CLI after installation, so the same environment can be used by the app and by manual probes:

`alpaca-mcp-server --transport stdio`

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub (submodule included).
2. On [share.streamlit.io](https://share.streamlit.io), create a new app from the repo.
   - **Main file path:** `dashboard/app.py`
   - **Advanced settings → Python version:** `3.11`
3. In **App → Settings → Secrets**, paste your keys (see `.streamlit/secrets.toml.example`):
   ```toml
   ALPACA_API_KEY = "..."
   ALPACA_SECRET_KEY = "..."
   GROQ_API_KEY = ""          # optional LLM (gsk_...), else XAI_API_KEY / FEATHERLESS_API_KEY
   ```
4. Deploy. `requirements.txt` installs the Alpaca MCP server from the `./mcp_server` submodule, so
   execution runs through MCP in the cloud too.

**Resilience:** the dashboard also has a direct Alpaca REST fallback for account/positions/clock, so it
stays fully functional even if the MCP subprocess is unavailable on the host. If the Cloud build ever
fails on the `./mcp_server` line (submodule not fetched), comment that line out of `requirements.txt` and
redeploy — the app runs on the REST fallback and market-data analytics are unaffected.

## Security

- Never commit .env
- Only ever use the Alpaca paper endpoint for this project
- Keep API keys in local environment variables only
- Keep the `mcp_server/` submodule checked out and installed locally; the trading app depends on it at runtime

## Demo narrative

This system is designed to feel like an AI-powered trading desk assistant: it reads market data, identifies a directional edge, checks the risk posture, and explains the trade decision before execution. That makes it easier to demonstrate in front of judges and easier to explain to non-technical stakeholders.

## Roadmap & Current Limitations

- Legacy stale positions from the pre-fix pricing bug are explicitly excluded from live risk scoring so they do not distort the current drawdown and delta exposure calculations.
- Strike/expiration selection occasionally chooses a contract that isn't listed in Alpaca's live option chain for certain tickers (observed with AMD, SPY, JPM, and XOM), resulting in an 'asset not found' rejection at order submission. This doesn't affect the core selection logic, which correctly targets near-the-money strikes when the chosen contract exists, it's an edge case in the interval/expiration matching for specific option chains that would be resolved by validating the selected symbol against the live chain before submission, rather than after.
