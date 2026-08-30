import streamlit as st

from agent.orchestrator import Orchestrator
from mcp.alpaca_mcp_client import AlpacaMCPClient


st.set_page_config(
    page_title="Quant Trading Agent",
    page_icon="📈",
    layout="wide",
)

st.markdown(
    """
    <style>
    .main {
        background: radial-gradient(circle at top left, rgba(14, 116, 144, 0.18), transparent 35%),
                    linear-gradient(180deg, #020817 0%, #0f172a 52%, #111827 100%);
        color: #f8fafc;
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    .topbar {
        background: rgba(15, 23, 42, 0.9);
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 18px;
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
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
        min-height: 116px;
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
    }
    .panel-header {
        color: #e2e8f0;
        font-size: 1.05rem;
        font-weight: 700;
        margin-bottom: 0.7rem;
    }
    .account-box {
        background: rgba(15, 23, 42, 0.72);
        border: 1px solid rgba(96, 165, 250, 0.22);
        border-radius: 16px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    .signal-banner {
        border-radius: 18px;
        padding: 1.2rem 1.1rem;
        border: 1px solid rgba(148, 163, 184, 0.18);
        background: rgba(15, 23, 42, 0.9);
    }
    .signal-word {
        font-size: 1.6rem;
        font-weight: 800;
        letter-spacing: 0.12em;
        text-transform: uppercase;
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
        background: linear-gradient(90deg, #f59e0b, #ef4444);
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
    if market_status_label in {"Open", "Closed"}:
        status_description = "Market is currently closed" if market_status_label == "Closed" else "Market is currently open"

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

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Signal</div>
                <div class="metric-value" style="color: {signal_style['fg']};">{signal.upper()}</div>
                <div class="metric-sub">Strength {score}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Risk score</div>
                <div class="metric-value">{risk}</div>
                <div class="metric-sub">{risk_level} risk</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Execution</div>
                <div class="metric-value" style="font-size: 1.4rem;">{strategy.upper()}</div>
                <div class="metric-sub">Options route</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col4:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Ticker</div>
                <div class="metric-value">{symbol}</div>
                <div class="metric-sub">Paper trading</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")

    left, right = st.columns([2.1, 1])
    with left:
        st.markdown('<div class="panel-header">Market overview</div>', unsafe_allow_html=True)
        chart_values = [
            {"date": i, "close": 100 + (i * 0.8) + (2 if signal == "bullish" else -1.5 if signal == "bearish" else 0.2)}
            for i in range(1, 21)
        ]
        st.line_chart(chart_values, x="date", y="close")

    with right:
        st.markdown('<div class="panel-header">Signal intelligence</div>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="signal-banner" style="background: {signal_style['bg']}; border-color: {signal_style['accent']}30;">
                <div class="signal-word" style="color: {signal_style['fg']};">{signal}</div>
                <div style="margin-top: 0.5rem; color: #e2e8f0; font-size: 0.9rem;">Confidence score: {score}</div>
                <div style="margin-top: 0.4rem; color: #cbd5e1; font-size: 0.85rem;">Risk posture: {risk_level}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="metric-sub">Portfolio risk level</div>', unsafe_allow_html=True)
        st.progress(float(risk) / 100.0)

    st.markdown("---")

    st.markdown('<div class="panel-header">Decision rationale</div>', unsafe_allow_html=True)
    st.info(explanation)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown('<div class="panel-header">Execution logic</div>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="panel">
                <div style="color: #e2e8f0; font-weight: 600;">Strategy</div>
                <div style="margin-top: 0.5rem; color: #93c5fd; font-size: 1.1rem; font-weight: 700;">{strategy.upper()}</div>
                <div style="margin-top: 0.9rem; color: #cbd5e1;">
                    Signal engine: {signal}<br>
                    Risk band: {risk_level}<br>
                    Ticker: {symbol}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_b:
        st.markdown('<div class="panel-header">Portfolio detail</div>', unsafe_allow_html=True)
        st.json({
            "signal": result["signal"],
            "risk": result["risk"],
            "strategy": result["strategy"],
        })

st.markdown("---")
st.caption("Built for adaptive options positioning, controlled risk, and explainable execution decisions.")
