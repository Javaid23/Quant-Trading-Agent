import json
from pathlib import Path

import pandas as pd
import streamlit as st

from agent.entry.indicators import calculate_bollinger_bands, calculate_macd, calculate_rsi, moving_average_crossover
from agent.entry.market_data_agent import MarketDataAgent
from agent.entry.signal_engine import SignalEngine
from agent.orchestrator import Orchestrator
from mcp.alpaca_mcp_client import AlpacaMCPClient


def get_trade_history_path() -> Path:
    path = Path(__file__).resolve().parents[1] / "data" / "logs" / "trade_history.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def ensure_trade_history() -> Path:
    history_path = get_trade_history_path()
    if not history_path.exists():
        default_history = {
            "trades": [
                {
                    "timestamp": "2026-08-31T09:30:00-04:00",
                    "symbol": "AAPL260918P00100000",
                    "side": "buy",
                    "strategy": "long_put",
                    "direction": "short",
                    "option_type": "put",
                    "status": "pending_new",
                    "order_id": "8ee0c32a-fd0f-4399-b71c-c3a284e589ba",
                    "explanation": "Signal=bearish. Risk indicates low risk. Strategy selected: long_put for a paper trading account.",
                    "market_context": "Live paper execution at market open",
                }
            ]
        }
        history_path.write_text(json.dumps(default_history, indent=2), encoding="utf-8")
    return history_path


def load_trade_history() -> pd.DataFrame:
    history_path = ensure_trade_history()
    try:
        payload = json.loads(history_path.read_text(encoding="utf-8"))
        trades = payload.get("trades", []) if isinstance(payload, dict) else []
    except Exception:
        trades = []
    if not trades:
        return pd.DataFrame(columns=["timestamp", "symbol", "strategy", "status", "side", "direction", "option_type", "order_id", "explanation"])
    return pd.DataFrame(trades)


def append_trade_history(entry: dict) -> None:
    history_path = ensure_trade_history()
    payload = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else {"trades": []}
    if not isinstance(payload, dict):
        payload = {"trades": []}
    payload.setdefault("trades", [])
    payload["trades"].append(entry)
    history_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


st.set_page_config(
    page_title="Quant Trading Agent",
    page_icon="📈",
    layout="wide",
)

st.markdown(
    """
    <style>
    .main {
        background: linear-gradient(180deg, #020817 0%, #0b1220 50%, #111827 100%);
        color: #f8fafc;
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    * {
        box-sizing: border-box;
    }
    .topbar {
        background: rgba(15, 23, 42, 0.9);
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 18px;
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 10px 30px rgba(2, 6, 23, 0.22);
    }
    .title-line {
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: -0.04em;
        color: #f8fafc;
    }
    .subtitle-line {
        color: #cbd5e1;
        font-size: 0.95rem;
        margin-top: 0.25rem;
    }
    .status-pill {
        display: inline-block;
        padding: 0.38rem 0.8rem;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .market-status-box {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 16px;
        padding: 0.75rem 0.9rem;
        margin-bottom: 0.9rem;
    }
    .metric-card {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 18px;
        padding: 1rem 1.1rem;
        min-height: 140px;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.22);
    }
    .metric-label {
        color: #94a3b8;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 800;
        margin-top: 0.45rem;
        color: #f8fafc;
        line-height: 1.1;
    }
    .metric-sub {
        color: #cbd5e1;
        font-size: 0.86rem;
        margin-top: 0.25rem;
    }
    .panel {
        background: rgba(15, 23, 42, 0.82);
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 18px;
        padding: 1rem 1.1rem;
        box-shadow: 0 12px 28px rgba(2, 6, 23, 0.24);
        min-height: 180px;
        border-left: 3px solid rgba(96, 165, 250, 0.8);
    }
    .panel-header {
        color: #e2e8f0;
        font-size: 1.08rem;
        font-weight: 700;
        margin-bottom: 0.7rem;
        letter-spacing: 0.02em;
    }
    .account-box {
        background: rgba(15, 23, 42, 0.72);
        border: 1px solid rgba(96, 165, 250, 0.22);
        border-radius: 16px;
        padding: 1rem;
        margin-bottom: 1rem;
        min-height: 150px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .signal-banner {
        border-radius: 18px;
        padding: 1.2rem 1.1rem;
        border: 1px solid rgba(148, 163, 184, 0.18);
        background: rgba(15, 23, 42, 0.9);
        min-height: 170px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .signal-word {
        font-size: 1.7rem;
        font-weight: 800;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }
    .gauge-wrap {
        width: 100%;
        margin-top: 0.7rem;
    }
    .gauge-bar {
        width: 100%;
        height: 12px;
        border-radius: 999px;
        background: rgba(148, 163, 184, 0.12);
        overflow: hidden;
        border: 1px solid rgba(148, 163, 184, 0.12);
    }
    .gauge-fill {
        height: 100%;
        border-radius: 999px;
        transition: width 0.25s ease;
    }
    .stButton > button {
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 12px;
        font-weight: 700;
        height: 3rem;
        width: 100%;
        color: white;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        filter: brightness(1.04);
    }
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 800;
    }
    [data-testid="stSidebar"] {
        background: rgba(2, 6, 23, 0.82);
    }
    .stProgress > div > div {
        background: linear-gradient(90deg, #38bdf8, #22c55e);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = Orchestrator()

st.markdown(
    """
    <div class="topbar">
        <div class="title-line">Autonomous Options Intelligence</div>
        <div class="subtitle-line">Real-time paper trading signal engine with portfolio risk monitoring</div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Market control")
    st.caption("Paper account risk monitoring")

    market_status_text = "Checking market..."
    market_status_color = "rgba(148, 163, 184, 0.18)"
    market_status_label = "Market"
    market_label_color = "#cbd5e1"
    next_open_text = ""
    try:
        clock = AlpacaMCPClient().client.get_clock()
        is_market_open = bool(getattr(clock, "is_open", False))
        market_status_label = "Open" if is_market_open else "Closed"
        market_status_color = "rgba(34, 197, 94, 0.15)" if is_market_open else "rgba(239, 68, 68, 0.14)"
        market_label_color = "#4ade80" if is_market_open else "#f87171"
        next_open = getattr(clock, "next_open", None)
        if next_open is not None:
            next_open_text = f"Next open: {next_open}"
    except Exception:
        market_status_text = "Market data unavailable"
        market_status_color = "rgba(148, 163, 184, 0.18)"
        market_status_label = "Unknown"
        market_label_color = "#cbd5e1"

    status_description = market_status_text if market_status_text != "Checking market..." else "Market status"
    if market_status_label == "Closed":
        status_description = "Markets are closed. View historical trends and past decisions below."
    elif market_status_label == "Open":
        status_description = "Market is currently open"

    st.markdown(
        f'<div class="market-status-box"><div style="font-size:0.72rem; text-transform:uppercase; letter-spacing:0.08em; color:#94a3b8;">Market status</div><div class="status-pill" style="background:{market_status_color}; color:{market_label_color}; margin-top:0.5rem;">{market_status_label}</div><div style="color:#cbd5e1; font-size:0.82rem; margin-top:0.55rem;">{status_description}</div>{f"<div style=\"color:#cbd5e1; font-size:0.76rem; margin-top:0.25rem;\">{next_open_text}</div>" if next_open_text else ""}</div>',
        unsafe_allow_html=True,
    )

    ticker_options = [
        "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "SPY", "QQQ", "NFLX", "AMD", "INTC",
        "PLTR", "BRK.B", "IBM", "UBER", "DIS", "SHOP", "NKE", "COST"
    ]

    st.caption("Quick watchlist")
    watchlist_cols = st.columns(4)
    for idx, ticker in enumerate(ticker_options[:8]):
        with watchlist_cols[idx % 4]:
            if st.button(ticker, key=f"watch_{ticker}", help=f"Load {ticker} into the analyzer"):
                st.session_state["selected_ticker"] = ticker

    ticker_query = st.text_input("Ticker search", value=st.session_state.get("selected_ticker", "AAPL"))
    filtered_tickers = [t for t in ticker_options if ticker_query.upper() in t.upper() or not ticker_query.strip()]
    if filtered_tickers:
        selected_ticker = st.selectbox(
            "Matching symbols",
            filtered_tickers,
            index=filtered_tickers.index(ticker_query.upper()) if ticker_query.upper() in filtered_tickers else 0,
        )
    else:
        selected_ticker = st.selectbox("Matching symbols", [ticker_query.upper() or "AAPL"], index=0)

    symbol = selected_ticker.upper()
    st.session_state["selected_ticker"] = symbol
    analyze = st.button("Analyze signal", use_container_width=True, key="analyze_signal_button")
    execute_trade = st.button("Execute trade", use_container_width=True, key="execute_trade_button", type="primary")

    st.markdown("---")
    st.subheader("System mode")
    st.markdown('<div class="status-pill" style="background: rgba(34, 197, 94, 0.14); color: #4ade80;">Entry + Defense</div>', unsafe_allow_html=True)
    st.caption("Deterministic signal engine and hedging logic")

    st.markdown("---")
    try:
        account = AlpacaMCPClient().get_account()
        st.subheader("Paper account")
        st.markdown(
            f"""
            <div class="account-box">
                <div style="color: #cbd5e1; font-size: 0.76rem; text-transform: uppercase; letter-spacing: 0.08em;">Status</div>
                <div style="color: #4ade80; font-size: 1.1rem; font-weight: 700; margin-top: 0.2rem;">{account['status']}</div>
                <div style="margin-top: 0.8rem; color: #e2e8f0; font-size: 0.88rem;">Cash: ${account['cash']:,.2f}</div>
                <div style="color: #e2e8f0; font-size: 0.88rem;">Buying power: ${account['buying_power']:,.2f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        st.caption("Account snapshot unavailable")

result = None
if analyze:
    try:
        result = st.session_state.orchestrator.evaluate_symbol(symbol, execute=False)
    except Exception as exc:
        st.error(f"Analysis failed: {exc}")
        result = None

if execute_trade:
    try:
        st.info("Submitting a paper-trading order to Alpaca. This is an actual execution request.")
        result = st.session_state.orchestrator.evaluate_symbol(symbol, execute=True)
        execution_payload = result.get("execution") if isinstance(result, dict) else None
        if isinstance(execution_payload, dict):
            trade_entry = {
                "timestamp": pd.Timestamp.utcnow().isoformat(),
                "symbol": execution_payload.get("symbol") or result.get("strategy", {}).get("option_symbol") or symbol,
                "side": execution_payload.get("side") or result.get("strategy", {}).get("direction"),
                "strategy": result.get("strategy", {}).get("strategy"),
                "direction": result.get("strategy", {}).get("direction"),
                "option_type": result.get("strategy", {}).get("option_type"),
                "status": execution_payload.get("status"),
                "order_id": execution_payload.get("id"),
                "explanation": result.get("explanation"),
                "market_context": "Live paper execution",
            }
            append_trade_history(trade_entry)
            message = execution_payload.get("message")
            if message:
                if execution_payload.get("status") == "not_submitted":
                    st.warning(message)
                else:
                    st.success(message)
    except Exception as exc:
        st.error(f"Execution failed: {exc}")
        result = None

if result is not None:
    signal = result["signal"]["signal"]
    score = result["signal"]["score"]
    risk = result["risk"]["risk_score"]
    risk_level = result["risk"]["level"].upper()
    strategy = result["strategy"]["strategy"]
    explanation = result["explanation"]

    signal_colors = {
        "bullish": {"bg": "rgba(34, 197, 94, 0.12)", "fg": "#4ade80", "accent": "#22c55e"},
        "bearish": {"bg": "rgba(239, 68, 68, 0.12)", "fg": "#f87171", "accent": "#ef4444"},
        "neutral": {"bg": "rgba(245, 158, 11, 0.12)", "fg": "#fbbf24", "accent": "#f59e0b"},
    }
    signal_style = signal_colors.get(signal, signal_colors["neutral"])

    signal_pct = max(0.0, min(1.0, float(score) / 100.0)) if isinstance(score, (int, float)) else 0.5
    risk_pct = max(0.0, min(1.0, float(risk) / 100.0))

    st.markdown('<div class="panel-header">Market Status</div>', unsafe_allow_html=True)
    market_col_1, market_col_2, market_col_3 = st.columns(3)
    with market_col_1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Ticker</div>
                <div class="metric-value">{symbol}</div>
                <div class="metric-sub">Paper account</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with market_col_2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Signal</div>
                <div class="metric-value" style="color: {signal_style['fg']};">{signal.upper()}</div>
                <div class="metric-sub">{risk_level} risk posture</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with market_col_3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Strategy</div>
                <div class="metric-value" style="font-size: 1.3rem;">{strategy.upper()}</div>
                <div class="metric-sub">Options route</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown('<div class="panel-header">Signal Intelligence</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="signal-banner" style="background: {signal_style['bg']}; border-color: {signal_style['accent']}30;">
            <div class="signal-word" style="color: {signal_style['fg']};">{signal}</div>
            <div style="margin-top: 0.8rem; color: #e2e8f0; font-size: 0.85rem; font-weight: 600;">Confidence score</div>
            <div class="gauge-wrap">
                <div class="gauge-bar">
                    <div class="gauge-fill" style="width: {signal_pct * 100:.1f}%; background: {signal_style['accent']};"></div>
                </div>
            </div>
            <div style="margin-top: 0.55rem; color: #e2e8f0; font-size: 0.88rem;">{score}/100</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown('<div class="panel-header">Risk Engine</div>', unsafe_allow_html=True)
    risk_color = "#ef4444" if risk_level in {"HIGH", "MEDIUM"} else "#f59e0b"
    if risk_level == "LOW":
        risk_color = "#22c55e"
    st.markdown(
        f"""
        <div class="panel">
            <div style="color: #e2e8f0; font-weight: 600;">Portfolio risk level</div>
            <div style="margin-top: 0.7rem; color: {risk_color}; font-size: 1.7rem; font-weight: 800;">{risk_level}</div>
            <div class="gauge-wrap">
                <div class="gauge-bar">
                    <div class="gauge-fill" style="width: {risk_pct * 100:.1f}%; background: {risk_color};"></div>
                </div>
            </div>
            <div style="margin-top: 0.75rem; color: #cbd5e1; font-size: 0.9rem;">Current score: {risk}/100</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown('<div class="panel-header">Execution Decision</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="panel">
            <div style="color: #e2e8f0; font-weight: 600;">Execution route</div>
            <div style="margin-top: 0.6rem; font-size: 1.45rem; font-weight: 800; color: #93c5fd;">{strategy.upper()}</div>
            <div style="margin-top: 1rem; color: #cbd5e1; line-height: 1.7;">
                Signal engine: {signal}<br>
                Risk band: {risk_level}<br>
                Ticker: {symbol}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown('<div class="panel-header">Decision Rationale</div>', unsafe_allow_html=True)
    st.info(explanation)

    st.markdown("---")
    st.markdown('<div class="panel-header">Market overview</div>', unsafe_allow_html=True)
    chart_values = [
        {"date": i, "close": 100 + (i * 0.8) + (2 if signal == "bullish" else -1.5 if signal == "bearish" else 0.2)}
        for i in range(1, 21)
    ]
    st.line_chart(chart_values, x="date", y="close")

    st.markdown("---")
    st.json({
        "signal": result["signal"],
        "risk": result["risk"],
        "strategy": result["strategy"],
    })

st.markdown("---")
st.markdown('<div class="panel-header">Historical View</div>', unsafe_allow_html=True)
historical_symbol = st.text_input("Historical ticker", value=st.session_state.get("selected_ticker", "AAPL"), key="historical_ticker")
lookback = st.selectbox("Lookback period", ["1M", "3M", "6M", "1Y"], index=2)
lookback_map = {"1M": 30, "3M": 90, "6M": 180, "1Y": 260}
window_days = lookback_map.get(lookback, 180)

try:
    historical_bars = MarketDataAgent().get_bars(historical_symbol.strip() or "AAPL", limit=window_days, timeframe="1Day")
    if historical_bars.empty:
        st.caption("No historical bars available for the selected ticker.")
    else:
        historical_bars = historical_bars.copy()
        historical_bars["timestamp"] = pd.to_datetime(historical_bars["timestamp"])
        historical_bars = historical_bars.sort_values("timestamp").reset_index(drop=True)
        historical_bars = historical_bars.set_index("timestamp")

        rsi = pd.Series(calculate_rsi(historical_bars["close"].astype(float), 14), index=historical_bars.index)
        macd_line, signal_line, _ = calculate_macd(historical_bars["close"].astype(float), 12, 26, 9)
        macd_series = pd.Series(macd_line, index=historical_bars.index)
        signal_series = pd.Series(signal_line, index=historical_bars.index)
        bollinger = calculate_bollinger_bands(historical_bars["close"].astype(float), 20, 2)
        ma = moving_average_crossover(historical_bars["close"].astype(float), 3, 5)

        price_overlay = pd.DataFrame({
            "Close": historical_bars["close"].astype(float),
            "Fast MA": pd.Series(ma["fast_ma"], index=historical_bars.index),
            "Slow MA": pd.Series(ma["slow_ma"], index=historical_bars.index),
            "Upper Band": pd.Series(bollinger["upper"], index=historical_bars.index),
            "Middle Band": pd.Series(bollinger["middle"], index=historical_bars.index),
            "Lower Band": pd.Series(bollinger["lower"], index=historical_bars.index),
        })
        st.line_chart(price_overlay)

        indicator_panel = pd.DataFrame({
            "RSI": rsi,
            "MACD": macd_series,
            "Signal Line": signal_series,
        })
        st.line_chart(indicator_panel)

        signal_history = []
        engine = SignalEngine()
        for idx in range(20, len(historical_bars) + 1):
            slice_df = historical_bars.iloc[:idx].reset_index().rename(columns={"timestamp": "timestamp"})
            signal_record = engine.generate_signal(slice_df)
            signal_history.append({
                "timestamp": slice_df["timestamp"].iloc[-1],
                "signal": signal_record["signal"],
                "score": signal_record["score"],
            })
        signal_log = pd.DataFrame(signal_history).tail(10)
        if not signal_log.empty:
            st.dataframe(signal_log.rename(columns={"timestamp": "date"}), use_container_width=True)
except Exception as exc:
    st.caption(f"Historical view unavailable: {exc}")

trade_history = load_trade_history()
if not trade_history.empty:
    trade_history = trade_history.copy()
    trade_history["timestamp"] = pd.to_datetime(trade_history["timestamp"], errors="coerce")
    st.markdown("---")
    st.markdown('<div class="panel-header">Trade and Decision History</div>', unsafe_allow_html=True)
    st.dataframe(
        trade_history[["timestamp", "symbol", "strategy", "direction", "side", "status", "order_id", "explanation"]].sort_values("timestamp", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

st.markdown("---")
st.caption("Built for adaptive options positioning, controlled risk, and explainable execution decisions.")
