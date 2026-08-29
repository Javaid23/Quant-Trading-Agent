# Quant Trading Agent

A paper-trading options strategy agent for the Alpaca AI Trading Agents Hackathon.

## Overview

This project builds an autonomous trading agent with:

- entry signals derived from technical indicators
- options-based trade execution on Alpaca paper accounts
- continuous portfolio risk monitoring and hedging
- plain-language explanations logged into a dashboard

## Setup

1. Create a Python virtual environment.
2. Install dependencies:
   pip install -r requirements.txt
3. Copy .env.example to .env and fill in your keys.
4. Run the project modules as they become available.

## Security

- Never commit .env
- Only ever use the Alpaca paper endpoint for this project
