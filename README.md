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

1. Create a Python virtual environment.
2. Install dependencies:
   pip install -r requirements.txt
3. Copy .env.example to .env and fill in your keys.
4. Run the app with Streamlit:
   streamlit run dashboard/app.py
5. Analyze a ticker from the dashboard watchlist or search box.

## Security

- Never commit .env
- Only ever use the Alpaca paper endpoint for this project
- Keep API keys in local environment variables only

## Demo narrative

This system is designed to feel like an AI-powered trading desk assistant: it reads market data, identifies a directional edge, checks the risk posture, and explains the trade decision before execution. That makes it easier to demonstrate in front of judges and easier to explain to non-technical stakeholders.
