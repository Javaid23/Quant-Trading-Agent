import altair as alt
import pandas as pd
import streamlit as st

from agent.entry.indicators import calculate_bollinger_bands, calculate_macd, calculate_rsi, moving_average_crossover
from agent.entry.market_data_agent import MarketDataAgent
from agent.entry.signal_engine import SignalEngine
from agent.orchestrator import Orchestrator
from agent.trade_log import TRADE_FIELDS, TradeLog

st.set_page_config(page_title="Quant Trading Agent", page_icon="📈", layout="wide")

WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "SPY", "QQQ", "NFLX",
    "AMD", "PLTR", "INTC", "UBER", "COIN", "DIS", "JPM", "BAC", "XOM", "COST",
]
QUICK_TICKERS = WATCHLIST[:8]
_trade_log = TradeLog()


# ----------------------------- helpers -----------------------------
def pget(position, key, default=None):
    if isinstance(position, dict):
        return position.get(key, default)
    return getattr(position, key, default)


def fnum(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@st.cache_data(ttl=300, show_spinner=False)
def fetch_daily_bars(symbol: str, limit: int) -> pd.DataFrame:
    try:
        return MarketDataAgent().get_bars(symbol, limit=limit, timeframe="1Day")
    except Exception:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])


@st.cache_data(ttl=300, show_spinner=False)
def compute_chart_data(symbol: str, window_days: int):
    bars = fetch_daily_bars(symbol, window_days)
    if bars is None or bars.empty:
        return None
    bars = bars.copy()
    bars["timestamp"] = pd.to_datetime(bars["timestamp"])
    bars = bars.sort_values("timestamp").reset_index(drop=True).set_index("timestamp")
    closes = bars["close"].astype(float)

    rsi = pd.Series(calculate_rsi(closes, 14), index=bars.index)
    macd_line, signal_line, _ = calculate_macd(closes, 12, 26, 9)
    bollinger = calculate_bollinger_bands(closes, 20, 2)
    ma = moving_average_crossover(closes, 3, 5)

    price_overlay = pd.DataFrame({
        "date": bars.index,
        "Close": closes,
        "Fast MA": pd.Series(ma["fast_ma"], index=bars.index),
        "Slow MA": pd.Series(ma["slow_ma"], index=bars.index),
        "Upper Band": pd.Series(bollinger["upper"], index=bars.index),
        "Lower Band": pd.Series(bollinger["lower"], index=bars.index),
    }).reset_index(drop=True)

    indicator_df = pd.DataFrame({
        "date": bars.index,
        "RSI": rsi,
        "MACD": pd.Series(macd_line, index=bars.index),
        "Signal Line": pd.Series(signal_line, index=bars.index),
    }).reset_index(drop=True)

    engine = SignalEngine()
    signal_history = []
    for idx in range(20, len(bars) + 1):
        slice_df = bars.iloc[:idx].reset_index()
        record = engine.generate_signal(slice_df)
        signal_history.append({"date": slice_df["timestamp"].iloc[-1], "signal": record["signal"], "score": record["score"]})
    signal_log = pd.DataFrame(signal_history).tail(12)
    return price_overlay, indicator_df, signal_log, int(len(bars))


def refresh_portfolio(force: bool = False) -> None:
    if not force and st.session_state.get("account_loaded"):
        return
    agent = getattr(st.session_state.orchestrator, "execution_agent", None)
    account, positions, clock = None, [], {}
    if agent is not None:
        try:
            account = agent.get_account_summary()
        except Exception:
            account = None
        try:
            positions = agent.client.get_all_positions() or []
        except Exception:
            positions = []
        try:
            clock = agent.get_market_clock()
        except Exception:
            clock = {}
    st.session_state["account"] = account
    st.session_state["positions"] = positions
    st.session_state["clock"] = clock
    st.session_state["last_refresh"] = pd.Timestamp.now(tz="UTC").strftime("%H:%M:%S UTC")
    st.session_state["account_loaded"] = True


def load_trade_history() -> pd.DataFrame:
    trades = _trade_log.load()
    return pd.DataFrame(trades) if trades else pd.DataFrame(columns=TRADE_FIELDS)


def positions_dataframe(positions) -> pd.DataFrame:
    rows = []
    for p in positions:
        rows.append({
            "Symbol": pget(p, "symbol"),
            "Qty": fnum(pget(p, "qty")),
            "Side": str(pget(p, "side", "")).upper(),
            "Avg Entry": fnum(pget(p, "avg_entry_price")),
            "Current": fnum(pget(p, "current_price")),
            "Mkt Value": fnum(pget(p, "market_value")),
            "Unreal P/L": fnum(pget(p, "unrealized_pl")),
            "P/L %": round(fnum(pget(p, "unrealized_plpc")) * 100, 2),
        })
    return pd.DataFrame(rows)


SIGNAL_COLORS = {
    "bullish": {"bg": "rgba(34, 197, 94, 0.12)", "fg": "#4ade80", "accent": "#22c55e"},
    "bearish": {"bg": "rgba(239, 68, 68, 0.12)", "fg": "#f87171", "accent": "#ef4444"},
    "neutral": {"bg": "rgba(245, 158, 11, 0.12)", "fg": "#fbbf24", "accent": "#f59e0b"},
    "no_data": {"bg": "rgba(148, 163, 184, 0.12)", "fg": "#cbd5e1", "accent": "#94a3b8"},
}


# ----------------------------- styling -----------------------------
st.markdown(
    """
    <style>
    .main { background: linear-gradient(180deg, #020817 0%, #0b1220 48%, #111827 100%); color: #f8fafc; }
    .block-container { padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1520px; }
    * { box-sizing: border-box; }
    .topbar {
        background: linear-gradient(135deg, rgba(15,23,42,0.96), rgba(30,41,59,0.94));
        border: 1px solid rgba(148,163,184,0.14); border-radius: 18px; padding: 1.05rem 1.3rem;
        margin-bottom: 0.9rem; box-shadow: 0 16px 32px rgba(2,6,23,0.24);
        display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.6rem;
    }
    .title-line { font-size: clamp(1.6rem, 2.6vw, 2.4rem); font-weight: 900; letter-spacing: -0.05em; line-height: 1.05; color: #f8fafc; text-shadow: 0 0 18px rgba(59,130,246,0.18); }
    .subtitle-line { color: #cbd5e1; font-size: 0.9rem; margin-top: 0.1rem; opacity: 0.9; }
    .status-pill { display: inline-block; padding: 0.42rem 0.82rem; border-radius: 999px; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
    .badge { display:inline-block; padding: 0.3rem 0.7rem; border-radius: 999px; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.04em; background: rgba(96,165,250,0.14); color:#93c5fd; border:1px solid rgba(96,165,250,0.3); }
    .metric-card { background: rgba(15,23,42,0.82); border: 1px solid rgba(148,163,184,0.16); border-radius: 16px; padding: 0.85rem 1rem; min-height: 104px; height: 100%; display: flex; flex-direction: column; justify-content: space-between; box-shadow: 0 12px 28px rgba(15,23,42,0.2); }
    .metric-label { color: #94a3b8; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em; }
    .metric-value { font-size: clamp(1.25rem, 1.8vw, 1.9rem); font-weight: 800; margin-top: 0.35rem; color: #f8fafc; line-height: 1.1; }
    .metric-sub { color: #cbd5e1; font-size: 0.8rem; margin-top: 0.2rem; }
    .panel { background: rgba(15,23,42,0.82); border: 1px solid rgba(148,163,184,0.14); border-radius: 16px; padding: 1rem 1.1rem; box-shadow: 0 12px 28px rgba(2,6,23,0.22); border-left: 3px solid rgba(96,165,250,0.8); }
    .panel-header { color: #e2e8f0; font-size: 1.02rem; font-weight: 700; margin: 0.4rem 0 0.6rem; letter-spacing: 0.02em; }
    .signal-banner { border-radius: 16px; padding: 1.1rem; border: 1px solid rgba(148,163,184,0.18); background: rgba(15,23,42,0.9); display: flex; flex-direction: column; justify-content: center; }
    .signal-word { font-size: 1.7rem; font-weight: 800; letter-spacing: 0.14em; text-transform: uppercase; }
    .gauge-bar { width: 100%; height: 12px; border-radius: 999px; background: rgba(148,163,184,0.12); overflow: hidden; border: 1px solid rgba(148,163,184,0.12); margin-top: 0.6rem; }
    .gauge-fill { height: 100%; border-radius: 999px; transition: width 0.25s ease; }
    .ai-box { background: rgba(15,23,42,0.82); border: 1px solid rgba(96,165,250,0.22); border-left: 3px solid #60a5fa; border-radius: 16px; padding: 1rem 1.1rem; color:#e2e8f0; line-height:1.6; }
    .stButton > button { border: 1px solid rgba(148,163,184,0.16); border-radius: 12px; font-weight: 700; height: 2.9rem; width: 100%; color: white; background: linear-gradient(180deg, rgba(30,41,59,0.9), rgba(15,23,42,0.94)); transition: all 0.2s ease; box-shadow: 0 10px 18px rgba(15,23,42,0.18); }
    .stButton > button:hover { transform: translateY(-1px); filter: brightness(1.08); }
    .stButton > button[kind="primary"] { background: linear-gradient(180deg, #ef4444, #dc2626); border-color: rgba(254,202,202,0.4); }
    [data-testid="stSidebar"] { background: rgba(2,6,23,0.82); border-right: 1px solid rgba(148,163,184,0.12); }
    .stTabs [data-baseweb="tab-list"] { gap: 0.3rem; }
    .stTabs [data-baseweb="tab"] { background: rgba(15,23,42,0.6); border-radius: 12px 12px 0 0; padding: 0.5rem 1rem; font-weight: 700; }
    .stTabs [aria-selected="true"] { background: rgba(96,165,250,0.16); color: #93c5fd; }
    .stDataFrame > div { background: rgba(15,23,42,0.7); border: 1px solid rgba(148,163,184,0.12); border-radius: 12px; }
    </style>
    """,
    unsafe_allow_html=True,
)

if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = Orchestrator()

refresh_portfolio(force=False)

account = st.session_state.get("account")
positions = st.session_state.get("positions", [])
clock = st.session_state.get("clock", {})
provider = getattr(st.session_state.orchestrator, "explainer", None)
provider_name = provider.provider if provider is not None else "none"

equity = fnum(pget(account, "equity", 0)) if account else 0.0
buying_power = fnum(pget(account, "buying_power", 0)) if account else 0.0
cash = fnum(pget(account, "cash", 0)) if account else 0.0
open_pl = sum(fnum(pget(p, "unrealized_pl", 0)) for p in positions)
is_open = bool(clock.get("is_open")) if isinstance(clock, dict) else False


# ----------------------------- sidebar -----------------------------
with st.sidebar:
    st.markdown('<div class="panel-header">Market control</div>', unsafe_allow_html=True)
    mk_label = "Open" if is_open else "Closed"
    mk_color = "rgba(34,197,94,0.15)" if is_open else "rgba(239,68,68,0.14)"
    mk_fg = "#4ade80" if is_open else "#f87171"
    next_open = clock.get("next_open") if isinstance(clock, dict) else None
    next_html = f'<div style="color:#cbd5e1;font-size:0.75rem;margin-top:0.4rem;">Next open: {next_open}</div>' if (next_open and not is_open) else ""
    st.markdown(
        f'<div class="panel" style="border-left-color:{mk_fg};"><div class="metric-label">Market status</div>'
        f'<div class="status-pill" style="background:{mk_color};color:{mk_fg};margin-top:0.5rem;">{mk_label}</div>{next_html}</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Data as of {st.session_state.get('last_refresh', '—')}")
    if st.button("🔄 Refresh account & positions", width="stretch", key="refresh_btn"):
        refresh_portfolio(force=True)
        st.rerun()

    st.markdown("---")
    st.markdown('<div class="panel-header">Ticker</div>', unsafe_allow_html=True)
    if "ticker_select" not in st.session_state:
        st.session_state["ticker_select"] = st.session_state.get("selected_ticker", "AAPL")
    st.caption("Quick pick")
    qcols = st.columns(4)
    for i, t in enumerate(QUICK_TICKERS):
        if qcols[i % 4].button(t, key=f"pick_{t}", width="stretch"):
            st.session_state["ticker_select"] = t
            st.rerun()
    # Scrollable, searchable dropdown of the full watchlist; accept_new_options lets you type any
    # Alpaca-tradable symbol that isn't in the list.
    current = st.session_state.get("ticker_select", "AAPL")
    ticker_options = WATCHLIST if current in WATCHLIST else [current] + WATCHLIST
    symbol = (st.selectbox("Choose or type a ticker", options=ticker_options, key="ticker_select", accept_new_options=True) or "AAPL").upper().strip()
    st.session_state["selected_ticker"] = symbol

    st.markdown("---")
    analyze = st.button("Analyze signal", width="stretch", key="analyze_btn")
    execute_trade = st.button("Execute trade", width="stretch", key="execute_btn", type="primary")
    defense_cycle = st.button("Run defense cycle", width="stretch", key="defense_btn")


# ----------------------------- actions -----------------------------
if analyze:
    try:
        st.session_state["result"] = st.session_state.orchestrator.evaluate_symbol(symbol, execute=False)
    except Exception as exc:
        st.session_state["result"] = None
        st.session_state["action_msg"] = ("error", f"Analysis failed: {exc}")

if execute_trade:
    try:
        result = st.session_state.orchestrator.evaluate_symbol(symbol, execute=True)
        st.session_state["result"] = result
        payload = result.get("execution") if isinstance(result, dict) else None
        if isinstance(payload, dict):
            _trade_log.append({
                "timestamp": pd.Timestamp.now(tz="UTC").isoformat(),
                "symbol": payload.get("symbol") or result.get("strategy", {}).get("option_symbol") or symbol,
                "side": payload.get("side") or result.get("strategy", {}).get("direction"),
                "strategy": result.get("strategy", {}).get("strategy"),
                "direction": result.get("strategy", {}).get("direction"),
                "option_type": result.get("strategy", {}).get("option_type"),
                "status": payload.get("status"),
                "order_id": payload.get("id"),
                "explanation": result.get("explanation"),
                "market_context": "Live paper execution",
            })
            msg = payload.get("message") or f"Order {payload.get('status', 'submitted')} for {payload.get('symbol', symbol)}"
            st.session_state["action_msg"] = ("warning" if payload.get("status") == "not_submitted" else "success", msg)
        refresh_portfolio(force=True)
    except Exception as exc:
        st.session_state["action_msg"] = ("error", f"Execution failed: {exc}")

if defense_cycle:
    try:
        st.session_state["defense"] = st.session_state.orchestrator.manage_open_positions(execute=True)
        refresh_portfolio(force=True)
    except Exception as exc:
        st.session_state["action_msg"] = ("error", f"Defense cycle failed: {exc}")


# ----------------------------- header + KPIs -----------------------------
st.markdown(
    '<div class="topbar"><div><div class="title-line">Quant Trading Agent</div>'
    '<div class="subtitle-line">Autonomous options desk · signal engine · risk defense · explainable execution</div></div></div>',
    unsafe_allow_html=True,
)


def kpi(col, label, value, sub="", color="#f8fafc"):
    col.markdown(
        f'<div class="metric-card"><div class="metric-label">{label}</div>'
        f'<div class="metric-value" style="color:{color}">{value}</div>'
        f'<div class="metric-sub">{sub}</div></div>',
        unsafe_allow_html=True,
    )


k = st.columns(5)
kpi(k[0], "Equity", f"${equity:,.0f}", "Paper account")
kpi(k[1], "Buying Power", f"${buying_power:,.0f}")
kpi(k[2], "Cash", f"${cash:,.0f}")
kpi(k[3], "Open P/L", f"${open_pl:,.0f}", "Unrealized", "#4ade80" if open_pl >= 0 else "#f87171")
kpi(k[4], "Open Positions", f"{len(positions)}", "Market open" if is_open else "Market closed", "#4ade80" if is_open else "#f87171")

if st.session_state.get("action_msg"):
    kind, text = st.session_state.pop("action_msg")
    getattr(st, kind)(text)

st.write("")
tab_agent, tab_portfolio, tab_scan, tab_charts, tab_history = st.tabs(
    ["🤖 Live Agent", "💼 Portfolio", "📡 Watchlist Scan", "📈 Charts", "🧾 History"]
)


# ----------------------------- tab: Live Agent -----------------------------
with tab_agent:
    result = st.session_state.get("result")
    if result is None:
        st.info("Pick a ticker in the sidebar and press **Analyze signal** to run the agent, or **Execute trade** to place a paper order.")
    elif result.get("status") != "ok":
        st.warning(f"{result.get('symbol', symbol)}: {result.get('explanation', 'No data available for this ticker.')}")
    else:
        signal = result["signal"]["signal"]
        score = result["signal"]["score"]
        risk = result["risk"]["risk_score"]
        risk_level = result["risk"]["level"].upper()
        strategy = result["strategy"]["strategy"]
        option_symbol = result["strategy"].get("option_symbol") or "—"
        style = SIGNAL_COLORS.get(signal, SIGNAL_COLORS["neutral"])
        signal_pct = max(0.0, min(1.0, (fnum(score) + 100.0) / 200.0))
        risk_pct = max(0.0, min(1.0, fnum(risk) / 100.0))
        risk_color = "#22c55e" if risk_level == "LOW" else ("#f59e0b" if risk_level == "MEDIUM" else "#ef4444")
        port_risk = result.get("portfolio_risk") or {}
        port_score = port_risk.get("risk_score") if isinstance(port_risk, dict) else None

        left, right = st.columns([1.1, 1])
        with left:
            st.markdown(
                f'<div class="signal-banner" style="background:{style["bg"]};border-color:{style["accent"]}55;">'
                f'<div class="metric-label">Signal for {result["symbol"]}</div>'
                f'<div class="signal-word" style="color:{style["fg"]};">{signal}</div>'
                f'<div style="margin-top:0.5rem;color:#e2e8f0;font-size:0.82rem;">Conviction</div>'
                f'<div class="gauge-bar"><div class="gauge-fill" style="width:{signal_pct*100:.1f}%;background:{style["accent"]};"></div></div>'
                f'<div style="margin-top:0.4rem;color:#e2e8f0;font-size:0.85rem;">Score {score}</div></div>',
                unsafe_allow_html=True,
            )
        with right:
            port_line = f'<div style="margin-top:0.5rem;color:#94a3b8;font-size:0.78rem;">Portfolio-wide risk: {port_score}/100</div>' if port_score is not None else ""
            st.markdown(
                f'<div class="panel" style="border-left-color:{risk_color};">'
                f'<div class="metric-label">Risk for {result["symbol"]}</div>'
                f'<div style="margin-top:0.4rem;color:{risk_color};font-size:1.6rem;font-weight:800;">{risk_level}</div>'
                f'<div class="gauge-bar"><div class="gauge-fill" style="width:{risk_pct*100:.1f}%;background:{risk_color};"></div></div>'
                f'<div style="margin-top:0.5rem;color:#cbd5e1;font-size:0.85rem;">Score {risk}/100</div>{port_line}</div>',
                unsafe_allow_html=True,
            )

        st.write("")
        d = st.columns(3)
        kpi(d[0], "Route", strategy.upper().replace("_", " "), "defense" if result["path"] == "defense" else "entry", "#93c5fd")
        kpi(d[1], "Contract", option_symbol if option_symbol != "—" else "None", "OCC option symbol")
        kpi(d[2], "Direction", str(result["strategy"].get("direction", "—")).upper(), "held" if result.get("has_symbol_position") else "new position")

        st.markdown('<div class="panel-header"> AI rationale</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="ai-box">{result["explanation"]}</div>', unsafe_allow_html=True)

        st.markdown('<div class="panel-header">Recent price</div>', unsafe_allow_html=True)
        overview = fetch_daily_bars(result["symbol"], 40)
        if overview is not None and not overview.empty:
            odf = overview.copy()
            odf["timestamp"] = pd.to_datetime(odf["timestamp"])
            st.line_chart(odf, x="timestamp", y="close", height=240)
        else:
            st.caption("No recent price data available.")


# ----------------------------- tab: Portfolio -----------------------------
with tab_portfolio:
    st.markdown('<div class="panel-header">Open positions</div>', unsafe_allow_html=True)
    if not positions:
        st.info("No open positions. Execute a trade or run the watchlist scan to open one.")
    else:
        pdf = positions_dataframe(positions)

        def _color(v):
            return "color:#4ade80" if v > 0 else ("color:#f87171" if v < 0 else "")

        fmt = {"Avg Entry": "${:,.2f}", "Current": "${:,.2f}", "Mkt Value": "${:,.2f}", "Unreal P/L": "${:,.2f}", "P/L %": "{:.2f}%", "Qty": "{:.0f}"}
        try:
            styled = pdf.style.map(_color, subset=["Unreal P/L", "P/L %"]).format(fmt)
        except AttributeError:
            styled = pdf.style.applymap(_color, subset=["Unreal P/L", "P/L %"]).format(fmt)
        st.dataframe(styled, width="stretch", hide_index=True)
        st.caption(f"{len(positions)} open position(s) · total unrealized P/L ${open_pl:,.2f}")

    st.markdown("---")
    st.markdown('<div class="panel-header">🛡️ Defense cycle</div>', unsafe_allow_html=True)
    st.caption("Reviews every open position and takes profit / stops out / exits near expiry. Use the sidebar **Run defense cycle** button.")
    defense = st.session_state.get("defense")
    if defense:
        st.write(f"Reviewed **{defense.get('evaluated', 0)}** positions · closing **{defense.get('to_close', 0)}**.")
        acts = defense.get("actions", [])
        if acts:
            st.dataframe(
                pd.DataFrame([
                    {"symbol": a["symbol"], "action": a["action"],
                     "P/L %": None if a.get("unrealized_plpc") is None else round(a["unrealized_plpc"] * 100, 1),
                     "days to expiry": a.get("days_to_expiry"), "reason": a["reason"]}
                    for a in acts
                ]),
                width="stretch", hide_index=True,
            )
        else:
            st.success("No position breached take-profit, stop-loss, or the expiry window.")


# ----------------------------- tab: Watchlist Scan -----------------------------
with tab_scan:
    st.markdown('<div class="panel-header">📡 Autonomous watchlist scan</div>', unsafe_allow_html=True)
    st.caption("Runs the signal engine + risk across the whole watchlist and shows what the agent would do on each. Read-only (no orders placed).")
    if st.button("Scan watchlist now", key="scan_btn"):
        with st.spinner("Scanning watchlist…"):
            st.session_state["scan"] = st.session_state.orchestrator.scan_watchlist(WATCHLIST)

    scanned = st.session_state.get("scan")
    if scanned:
        rows = []
        for r in scanned:
            rows.append({
                "symbol": r.get("symbol", "?"),
                "signal": r.get("signal", "no_data"),
                "score": r.get("score"),
                "strategy": r.get("strategy", "—"),
                "risk": r.get("risk"),
                "risk level": (r.get("risk_level") or "—"),
            })
        scan_df = pd.DataFrame(rows)

        def _sig_color(v):
            return {"bullish": "color:#4ade80", "bearish": "color:#f87171", "neutral": "color:#fbbf24"}.get(v, "color:#cbd5e1")

        try:
            styled = scan_df.style.map(_sig_color, subset=["signal"])
        except AttributeError:
            styled = scan_df.style.applymap(_sig_color, subset=["signal"])
        st.dataframe(styled, width="stretch", hide_index=True)
        actionable = [r for r in rows if r["strategy"] not in ("hold", "—")]
        st.caption(f"{len(actionable)} actionable signal(s) of {len(rows)} scanned.")
    else:
        st.info("Press **Scan watchlist now** to see signals across all tickers.")


# ----------------------------- tab: Charts -----------------------------
with tab_charts:
    st.markdown(f'<div class="panel-header">📈 {symbol} — technical view</div>', unsafe_allow_html=True)
    lookback = st.selectbox("Lookback period", ["1M", "3M", "6M", "1Y"], index=2, key="lookback")
    window = {"1M": 30, "3M": 90, "6M": 180, "1Y": 260}[lookback]
    data = compute_chart_data(symbol, window)
    if data is None:
        st.caption("No historical bars available for this ticker.")
    else:
        price_overlay, indicator_df, signal_log, n_bars = data
        st.caption(f"{n_bars} daily bars")
        price = alt.Chart(price_overlay).mark_line(color="#7dd3fc", strokeWidth=2.5).encode(
            x=alt.X("date:T", axis=alt.Axis(format="%b %d", title="Date")), y=alt.Y("Close:Q", title="Price", scale=alt.Scale(zero=False)))
        fast = alt.Chart(price_overlay).mark_line(color="#facc15", strokeWidth=1.5).encode(x="date:T", y=alt.Y("Fast MA:Q", scale=alt.Scale(zero=False)))
        slow = alt.Chart(price_overlay).mark_line(color="#a78bfa", strokeWidth=1.5).encode(x="date:T", y=alt.Y("Slow MA:Q", scale=alt.Scale(zero=False)))
        band = alt.Chart(price_overlay).mark_area(opacity=0.12, color="#22c55e").encode(x="date:T", y="Upper Band:Q", y2="Lower Band:Q")
        st.altair_chart((band + price + fast + slow).properties(height=340), width="stretch")

        c1, c2 = st.columns(2)
        with c1:
            st.caption("RSI (14)")
            st.altair_chart(
                alt.Chart(indicator_df).mark_line(color="#f59e0b", strokeWidth=2).encode(
                    x=alt.X("date:T", axis=alt.Axis(format="%b %d", title="Date")), y=alt.Y("RSI:Q", scale=alt.Scale(domain=(0, 100)))).properties(height=220),
                width="stretch",
            )
        with c2:
            st.caption("MACD")
            st.altair_chart(
                alt.Chart(indicator_df).mark_line(color="#34d399", strokeWidth=2).encode(
                    x=alt.X("date:T", axis=alt.Axis(format="%b %d", title="Date")), y="MACD:Q").properties(height=220),
                width="stretch",
            )
        st.markdown('<div class="panel-header">Signal history (last 12 bars)</div>', unsafe_allow_html=True)
        st.dataframe(signal_log, width="stretch", hide_index=True)


# ----------------------------- tab: History -----------------------------
with tab_history:
    st.markdown('<div class="panel-header">🧾 Trade & decision history</div>', unsafe_allow_html=True)
    hist = load_trade_history()
    if hist.empty:
        st.info("No trades logged yet. Execute a trade to populate the history.")
    else:
        hist = hist.copy()
        hist["timestamp"] = pd.to_datetime(hist["timestamp"], errors="coerce")
        cols = [c for c in ["timestamp", "symbol", "strategy", "direction", "side", "status", "explanation"] if c in hist.columns]
        st.dataframe(hist[cols].sort_values("timestamp", ascending=False), width="stretch", hide_index=True)
        st.caption(f"{len(hist)} logged decision(s).")

st.markdown("---")
st.caption("Paper trading only · adaptive options positioning, controlled risk, and explainable execution. Not investment advice.")
