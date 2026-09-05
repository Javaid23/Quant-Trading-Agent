import json
import os
import sys
from pathlib import Path

# Ensure the repo root is importable when Streamlit runs dashboard/app.py directly (e.g. on Streamlit
# Cloud, where PYTHONPATH is not set and only the dashboard/ folder is on sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import altair as alt
import pandas as pd
import streamlit as st

from agent.entry.indicators import calculate_macd, calculate_rsi
from agent.entry.market_data_agent import MarketDataAgent
from agent.orchestrator import Orchestrator
from agent.trade_log import TradeLog

try:
    from streamlit_lightweight_charts import renderLightweightCharts
    HAS_CHARTS = True
except Exception:
    HAS_CHARTS = False

st.set_page_config(page_title="Quant Trading Agent", page_icon="📈", layout="wide")

# On Streamlit Cloud, credentials live in st.secrets; mirror them into env vars so os.getenv works
# everywhere (execution agent, market data, explainer) without a local .env file.
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str) and not os.environ.get(_k):
            os.environ[_k] = _v
except Exception:
    pass

WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "SPY", "QQQ", "NFLX",
    "AMD", "PLTR", "INTC", "UBER", "COIN", "DIS", "JPM", "BAC", "XOM", "COST",
]
QUICK_TICKERS = WATCHLIST[:8]
_trade_log = TradeLog()
_SUMMARY_PATH = Path(__file__).resolve().parents[1] / "demo" / "backtest_summary.json"


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


@st.cache_data(ttl=180, show_spinner=False)
def fetch_portfolio_history(period: str = "1M", timeframe: str = "1D") -> pd.DataFrame:
    """Alpaca portfolio equity curve (unix seconds + equity) for the account (best effort)."""
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import GetPortfolioHistoryRequest

        client = TradingClient(os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY"), paper=True)
        history = client.get_portfolio_history(GetPortfolioHistoryRequest(period=period, timeframe=timeframe))
        ts = list(getattr(history, "timestamp", []) or [])
        eq = list(getattr(history, "equity", []) or [])
        rows = [(int(t), fnum(e)) for t, e in zip(ts, eq) if e is not None and fnum(e) > 0]
        return pd.DataFrame(rows, columns=["ts", "equity"]).drop_duplicates("ts")
    except Exception:
        return pd.DataFrame(columns=["ts", "equity"])


def equity_area_config(df: pd.DataFrame, up: bool):
    color = "#34d399" if up else "#f87171"
    top = "rgba(52,211,153,0.28)" if up else "rgba(248,113,113,0.28)"
    data = [{"time": int(r["ts"]), "value": round(float(r["equity"]), 2)} for _, r in df.iterrows()]
    return [{
        "chart": {
            "height": 320,
            "layout": {"background": {"type": "solid", "color": "#171d28"}, "textColor": "#8b93a7", "fontFamily": "Inter, sans-serif"},
            "grid": {"vertLines": {"color": "rgba(148,163,184,0.04)"}, "horzLines": {"color": "rgba(148,163,184,0.06)"}},
            "rightPriceScale": {"borderColor": "rgba(148,163,184,0.12)"},
            "timeScale": {"borderColor": "rgba(148,163,184,0.12)", "timeVisible": True, "secondsVisible": False},
            "crosshair": {"mode": 1},
        },
        "series": [{"type": "Area", "data": data, "options": {"lineColor": color, "lineWidth": 2, "topColor": top, "bottomColor": "rgba(23,29,40,0.02)", "priceLineVisible": False}}],
    }]


@st.cache_data(ttl=600, show_spinner=False)
def load_backtest_summary() -> dict:
    try:
        return json.loads(_SUMMARY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _trading_client():
    from alpaca.trading.client import TradingClient
    return TradingClient(os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY"), paper=True)


def fetch_account_rest():
    try:
        a = _trading_client().get_account()
        return {"account_number": getattr(a, "account_number", None), "status": str(getattr(a, "status", "")),
                "cash": fnum(a.cash), "buying_power": fnum(a.buying_power),
                "portfolio_value": fnum(getattr(a, "portfolio_value", a.equity)), "equity": fnum(a.equity)}
    except Exception:
        return None


def fetch_positions_rest():
    try:
        return [
            {"symbol": p.symbol, "qty": p.qty, "side": str(getattr(p, "side", "")).split(".")[-1].lower(),
             "avg_entry_price": p.avg_entry_price, "current_price": getattr(p, "current_price", None),
             "market_value": p.market_value, "unrealized_pl": p.unrealized_pl, "unrealized_plpc": p.unrealized_plpc}
            for p in _trading_client().get_all_positions()
        ]
    except Exception:
        return []


def fetch_clock_rest():
    try:
        c = _trading_client().get_clock()
        return {"is_open": bool(c.is_open), "next_open": str(c.next_open), "next_close": str(c.next_close)}
    except Exception:
        return {}


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
    # REST fallback so the dashboard still populates if the MCP subprocess is unavailable (e.g. on cloud).
    if not account:
        account = fetch_account_rest()
    if not positions:
        positions = fetch_positions_rest()
    if not clock:
        clock = fetch_clock_rest()
    st.session_state["account"] = account
    st.session_state["positions"] = positions
    st.session_state["clock"] = clock
    st.session_state["last_refresh"] = pd.Timestamp.now(tz="UTC").strftime("%H:%M:%S UTC")
    st.session_state["account_loaded"] = True


def load_trade_history() -> pd.DataFrame:
    trades = _trade_log.load()
    return pd.DataFrame(trades) if trades else pd.DataFrame(columns=["timestamp", "symbol", "side", "strategy", "status", "explanation"])


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


def candlestick_config(bars: pd.DataFrame):
    df = bars.copy()
    df["t"] = pd.to_datetime(df["timestamp"]).dt.strftime("%Y-%m-%d")
    df = df.drop_duplicates("t")
    candles = [
        {"time": r["t"], "open": round(fnum(r["open"]), 2), "high": round(fnum(r["high"]), 2),
         "low": round(fnum(r["low"]), 2), "close": round(fnum(r["close"]), 2)}
        for _, r in df.iterrows()
    ]
    close = df["close"].astype(float)
    sma = close.rolling(20).mean()
    ema = close.ewm(span=50, adjust=False).mean()
    sma_data = [{"time": t, "value": round(v, 2)} for t, v in zip(df["t"], sma) if pd.notna(v)]
    ema_data = [{"time": t, "value": round(v, 2)} for t, v in zip(df["t"], ema) if pd.notna(v)]
    return [{
        "chart": {
            "height": 440,
            "layout": {"background": {"type": "solid", "color": "#141a23"}, "textColor": "#8b93a7", "fontFamily": "Inter, sans-serif"},
            "grid": {"vertLines": {"color": "rgba(148,163,184,0.05)"}, "horzLines": {"color": "rgba(148,163,184,0.05)"}},
            "rightPriceScale": {"borderColor": "rgba(148,163,184,0.15)"},
            "timeScale": {"borderColor": "rgba(148,163,184,0.15)", "timeVisible": True},
            "crosshair": {"mode": 0},
        },
        "series": [
            {"type": "Candlestick", "data": candles, "options": {"upColor": "#34d399", "downColor": "#f87171", "borderVisible": False, "wickUpColor": "#34d399", "wickDownColor": "#f87171"}},
            {"type": "Line", "data": sma_data, "options": {"color": "#f6c453", "lineWidth": 2, "title": "SMA 20", "priceLineVisible": False}},
            {"type": "Line", "data": ema_data, "options": {"color": "#60a5fa", "lineWidth": 2, "title": "EMA 50", "priceLineVisible": False}},
        ],
    }]


SIGNAL_COLORS = {"bullish": "#34d399", "bearish": "#f87171", "neutral": "#f6c453", "no_data": "#94a3b8"}
REGIME = {"bullish": "BULLISH", "bearish": "BEARISH", "neutral": "SIDEWAYS", "no_data": "NO DATA"}


# ----------------------------- theme -----------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');
    html, body, [class*="css"], .stMarkdown, .stMetric { font-family: 'Inter', system-ui, -apple-system, sans-serif; }
    .main, .stApp { background: radial-gradient(1100px 520px at 20% -10%, #151b25 0%, #10151d 45%, #0c1017 100%); color: #e6e9f0; }
    .block-container { padding-top: 0.6rem; padding-bottom: 3rem; max-width: 1560px; }
    #MainMenu, footer { visibility: hidden; }
    [data-testid="stHeader"] { background: transparent; height: 0; min-height: 0; }
    [data-testid="stToolbar"] { right: 0.5rem; top: 0.2rem; }
    .topbar { display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.9rem;
        background: linear-gradient(135deg, #171d28, #131922); border: 1px solid rgba(148,163,184,0.12);
        border-radius: 16px; padding: 1rem 1.35rem; margin-bottom: 1rem; box-shadow: 0 10px 30px rgba(0,0,0,0.28); }
    .title-line { font-size: clamp(1.3rem,2.2vw,1.85rem); font-weight: 800; letter-spacing: -0.01em; color: #f4f6fb; }
    .title-line .accent { color: #f6c453; }
    .subtitle-line { color: #8b93a7; font-size: 0.82rem; margin-top: 0.2rem; }
    .pill-row { display:flex; gap:0.5rem; flex-wrap:wrap; }
    .pill { display:inline-flex; align-items:center; gap:0.45rem; padding:0.34rem 0.78rem; border-radius:999px; font-size:0.7rem;
        font-weight:600; letter-spacing:0.01em; border:1px solid rgba(148,163,184,0.16); color:#c7cedd; background: rgba(148,163,184,0.05); }
    .dot { width:8px; height:8px; border-radius:50%; background:#34d399; box-shadow:0 0 6px rgba(52,211,153,0.6); }
    .dot.off { background:#f6c453; box-shadow:0 0 6px rgba(246,196,83,0.55); }
    [data-testid="stHorizontalBlock"] { align-items: stretch; }
    .kpi { background: #171d28; border:1px solid rgba(148,163,184,0.12); border-radius:14px; padding:0.9rem 1.05rem;
        box-shadow: 0 8px 24px rgba(0,0,0,0.18); height:100%; min-height:118px; display:flex; flex-direction:column; justify-content:space-between; }
    .kpi-label { color:#8b93a7; font-size:0.72rem; font-weight:600; letter-spacing:0.03em; text-transform:uppercase; }
    .kpi-value { font-family:'JetBrains Mono', monospace; font-size: clamp(1.2rem,1.85vw,1.65rem); font-weight:700; margin-top:0.35rem; color:#f4f6fb; }
    .kpi-sub { color:#8b93a7; font-size:0.76rem; margin-top:0.25rem; }
    .card { background: #171d28; border:1px solid rgba(148,163,184,0.12); border-left:3px solid #f6c453;
        border-radius:14px; padding:0.9rem 1.05rem; margin-bottom:0.7rem; box-shadow: 0 8px 24px rgba(0,0,0,0.16); }
    .card-title { color:#c7cedd; font-size:0.74rem; letter-spacing:0.01em; text-transform:uppercase; font-weight:700; display:flex; justify-content:space-between; align-items:center; }
    .card-body { color:#cdd4e0; margin-top:0.4rem; font-size:0.94rem; line-height:1.55; }
    .verdict { font-size:0.66rem; font-weight:700; letter-spacing:0.02em; padding:0.18rem 0.55rem; border-radius:7px; }
    .v-pass { background:rgba(52,211,153,0.14); color:#34d399; }
    .v-warn { background:rgba(246,196,83,0.16); color:#f6c453; }
    .v-fail { background:rgba(248,113,113,0.14); color:#f87171; }
    .section-h { color:#c7cedd; font-size:0.86rem; letter-spacing:0.01em; font-weight:700; margin:0.5rem 0 0.6rem; }
    .stButton > button { font-family:'Inter', sans-serif; border:1px solid rgba(148,163,184,0.18); border-radius:11px; font-weight:600;
        font-size:0.82rem; height:2.7rem; width:100%; color:#e6e9f0; background: #1a212c; transition: all 0.15s ease; }
    .stButton > button:hover { border-color:#f6c453; color:#f6c453; }
    .stButton > button[kind="primary"] { background: linear-gradient(180deg, #f6c453, #eab308); border:none; color:#1a1408; font-weight:700; }
    [data-testid="stSidebar"] { background: #0e131b; border-right:1px solid rgba(148,163,184,0.1); }
    .stTabs [data-baseweb="tab-list"] { gap:0.4rem; border-bottom:1px solid rgba(148,163,184,0.12); }
    .stTabs [data-baseweb="tab"] { background:transparent; font-size:0.86rem; font-weight:600; color:#8b93a7; }
    .stTabs [aria-selected="true"] { color:#f6c453; border-bottom:2px solid #f6c453; }
    .stDataFrame > div { background: #141a23; border:1px solid rgba(148,163,184,0.1); border-radius:12px; }
    /* Sidebar readability: keep ticker text on one line + brighten select/input (no button recolor) */
    [data-testid="stSidebar"] .stButton > button { white-space:nowrap; overflow:visible; padding:0 0.4rem; }
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] .stCaption { color:#c7cedd !important; }
    [data-testid="stSidebar"] [data-baseweb="select"] * { color:#f4f6fb !important; }
    [data-testid="stSidebar"] input { color:#f4f6fb !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Recreate the orchestrator if it is missing or a stale instance from an earlier code version is cached
# in this session (Streamlit keeps session_state across reruns, so an old build can leave a stale object).
if "orchestrator" not in st.session_state or not hasattr(st.session_state.orchestrator, "scan_watchlist"):
    if not os.getenv("ALPACA_API_KEY") or not os.getenv("ALPACA_SECRET_KEY"):
        st.error(
            "⚠️ **Alpaca credentials not configured.**\n\n"
            "Add these in **Manage app → Settings → Secrets** (top-level, exactly as shown), then reboot:\n\n"
            "```toml\nALPACA_API_KEY = \"your_paper_key\"\nALPACA_SECRET_KEY = \"your_paper_secret\"\n```"
        )
        st.stop()
    try:
        st.session_state.orchestrator = Orchestrator()
        st.session_state["account_loaded"] = False
    except Exception as exc:
        st.error(f"Failed to initialize the trading agent: {exc}")
        st.stop()

refresh_portfolio(force=False)
account = st.session_state.get("account")
positions = st.session_state.get("positions", [])
clock = st.session_state.get("clock", {})
summary = load_backtest_summary()

equity = fnum(pget(account, "equity", 0)) if account else 0.0
buying_power = fnum(pget(account, "buying_power", 0)) if account else 0.0
cash = fnum(pget(account, "cash", 0)) if account else 0.0
open_pl = sum(fnum(pget(p, "unrealized_pl", 0)) for p in positions)
is_open = bool(clock.get("is_open")) if isinstance(clock, dict) else False
account_ok = account is not None


# ----------------------------- sidebar -----------------------------
with st.sidebar:
    st.markdown('<div class="section-h">Ticker</div>', unsafe_allow_html=True)
    if "ticker_select" not in st.session_state:
        st.session_state["ticker_select"] = st.session_state.get("selected_ticker", "AAPL")
    st.caption("Quick pick")
    qcols = st.columns(2)
    for i, t in enumerate(QUICK_TICKERS):
        if qcols[i % 2].button(t, key=f"pick_{t}", width="stretch"):
            st.session_state["ticker_select"] = t
            st.rerun()
    current = st.session_state.get("ticker_select", "AAPL")
    ticker_options = WATCHLIST if current in WATCHLIST else [current] + WATCHLIST
    symbol = (st.selectbox("Choose or type a ticker", options=ticker_options, key="ticker_select", accept_new_options=True) or "AAPL").upper().strip()
    st.session_state["selected_ticker"] = symbol

    st.markdown("---")
    analyze = st.button("▸ Analyze", width="stretch", key="analyze_btn")
    execute_trade = st.button("▸ Execute trade", width="stretch", key="execute_btn", type="primary")
    defense_cycle = st.button("▸ Defense cycle", width="stretch", key="defense_btn")
    if st.button("↻ Refresh account", width="stretch", key="refresh_btn"):
        refresh_portfolio(force=True)
        fetch_portfolio_history.clear()
        st.rerun()
    st.caption(f"Data · {st.session_state.get('last_refresh', '—')}")


# ----------------------------- actions -----------------------------
if analyze:
    try:
        st.session_state["result"] = st.session_state.orchestrator.evaluate_symbol(symbol, execute=False)
    except Exception as exc:
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
            msg = payload.get("message") or f"Order {payload.get('status', 'submitted')} · {payload.get('symbol', symbol)}"
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


# ----------------------------- header + status pills -----------------------------
def pill(label, on=True):
    return f'<span class="pill"><span class="dot {"" if on else "off"}"></span>{label}</span>'


mkt_pill = pill("MARKET · LIVE", True) if is_open else pill("MARKET · CLOSED", False)
st.markdown(
    '<div class="topbar"><div><div class="title-line"><span class="accent">◈</span> QUANT TRADING AGENT</div>'
    '<div class="subtitle-line">Autonomous Options Desk · Alpaca MCP · Explainable AI</div></div>'
    f'<div class="pill-row">{mkt_pill}{pill("ALPACA · CONNECTED", account_ok)}{pill("PAPER · ACTIVE", True)}{pill("AI ENGINE · RUNNING", True)}</div></div>',
    unsafe_allow_html=True,
)


def kpi(col, label, value, sub="", color="#f4f6fb"):
    col.markdown(
        f'<div class="kpi"><div class="kpi-label">{label}</div><div class="kpi-value" style="color:{color}">{value}</div>'
        f'<div class="kpi-sub">{sub or "&nbsp;"}</div></div>',
        unsafe_allow_html=True,
    )


k = st.columns(5)
kpi(k[0], "Portfolio Value", f"${equity:,.2f}", "Alpaca paper account")
kpi(k[1], "Open P/L", f"${open_pl:,.2f}", "Unrealized", "#34d399" if open_pl >= 0 else "#f87171")
kpi(k[2], "Cash Reserve", f"${cash:,.2f}", "Settled cash")
kpi(k[3], "Buying Power", f"${buying_power:,.2f}", "Available to trade")
kpi(k[4], "Open Positions", f"{len(positions)}", "Market open" if is_open else "Market closed", "#34d399" if is_open else "#f59e0b")

if st.session_state.get("action_msg"):
    kind, text = st.session_state.pop("action_msg")
    getattr(st, kind)(text)

st.write("")
tab_dash, tab_chart, tab_council, tab_trades, tab_lab, tab_port = st.tabs(
    ["◧ Dashboard", "📈 Live Chart", "🛡 AI Council", "🔎 Trade Explorer", "🧪 Strategy Lab", "💼 Portfolio"]
)
result = st.session_state.get("result")


# ----------------------------- Dashboard -----------------------------
with tab_dash:
    left, right = st.columns([1.6, 1])
    with left:
        hdr, toggle = st.columns([1, 1])
        with hdr:
            st.markdown('<div class="section-h">◈ Portfolio Performance · <span style="color:#34d399;">● LIVE</span></div>', unsafe_allow_html=True)
        with toggle:
            tf = st.segmented_control("tf", ["1D", "1W", "1M"], default="1M", label_visibility="collapsed", key="perf_tf") or "1M"
        period, tframe = {"1D": ("1D", "5Min"), "1W": ("1W", "1H"), "1M": ("1M", "1D")}[tf]
        hist = fetch_portfolio_history(period, tframe)

        if hist is not None and not hist.empty and len(hist) > 1:
            first, last = float(hist["equity"].iloc[0]), float(hist["equity"].iloc[-1])
            net = last - first
            ret = (net / first * 100) if first else 0.0
            up = net >= 0
            pcolor = "#34d399" if up else "#f87171"
            s = st.columns(3)

            def stat(col, label, value, color="#f4f6fb"):
                col.markdown(f'<div class="kpi-label">{label}</div><div style="font-family:JetBrains Mono,monospace;font-size:1.4rem;font-weight:700;color:{color};margin-top:0.1rem;">{value}</div>', unsafe_allow_html=True)

            stat(s[0], "Portfolio Equity", f"${last:,.2f}")
            stat(s[1], "Net P/L", f"{'+' if up else ''}{net:,.2f}", pcolor)
            stat(s[2], "Return", f"{'+' if up else ''}{ret:.2f}%", pcolor)
            st.write("")
            if HAS_CHARTS:
                try:
                    renderLightweightCharts(equity_area_config(hist, up), key=f"eq_{tf}")
                except Exception:
                    st.line_chart(hist.assign(t=pd.to_datetime(hist["ts"], unit="s")), x="t", y="equity", height=300)
            else:
                st.line_chart(hist.assign(t=pd.to_datetime(hist["ts"], unit="s")), x="t", y="equity", height=300)
        else:
            st.caption("Equity history will populate as the account trades. Try a wider timeframe.")
    with right:
        st.markdown('<div class="section-h">◈ Live Watchlist</div>', unsafe_allow_html=True)
        wl = st.session_state.get("wl_quotes")
        if st.button("↻ Refresh quotes", key="wl_refresh", width="stretch") or wl is None:
            try:
                bars_map = st.session_state.orchestrator.market_agent.get_bars_multi(WATCHLIST[:8], limit=5, timeframe="1Day")
                wl = []
                for s in WATCHLIST[:8]:
                    b = bars_map.get(s)
                    if b is not None and not b.empty and len(b) >= 2:
                        last, prev = float(b["close"].iloc[-1]), float(b["close"].iloc[-2])
                        wl.append({"Symbol": s, "Price": round(last, 2), "Chg %": round((last - prev) / prev * 100, 2)})
                st.session_state["wl_quotes"] = wl
            except Exception:
                wl = []
        if wl:
            wdf = pd.DataFrame(wl)
            try:
                styled = wdf.style.map(lambda v: "color:#34d399" if v > 0 else ("color:#f87171" if v < 0 else ""), subset=["Chg %"]).format({"Price": "${:,.2f}", "Chg %": "{:+.2f}%"})
            except AttributeError:
                styled = wdf
            st.dataframe(styled, width="stretch", hide_index=True, height=320)


# ----------------------------- Live Chart -----------------------------
with tab_chart:
    st.markdown(f'<div class="section-h">📈 {symbol} · Daily · SMA 20 / EMA 50</div>', unsafe_allow_html=True)
    bars = fetch_daily_bars(symbol, 180)
    if bars is None or bars.empty:
        st.caption("No price data for this ticker.")
    else:
        if HAS_CHARTS:
            try:
                renderLightweightCharts(candlestick_config(bars), key=f"cs_{symbol}")
            except Exception as exc:
                st.caption(f"Chart component unavailable: {exc}")
                st.line_chart(bars.assign(timestamp=pd.to_datetime(bars["timestamp"])), x="timestamp", y="close", height=360)
        else:
            st.line_chart(bars.assign(timestamp=pd.to_datetime(bars["timestamp"])), x="timestamp", y="close", height=360)

        # RSI + MACD sub-charts
        closes = bars["close"].astype(float)
        idf = pd.DataFrame({
            "date": pd.to_datetime(bars["timestamp"]),
            "RSI": calculate_rsi(closes, 14),
            "MACD": calculate_macd(closes, 12, 26, 9)[0],
        })
        c1, c2 = st.columns(2)
        with c1:
            st.caption("RSI (14)")
            st.altair_chart(alt.Chart(idf).mark_line(color="#f59e0b").encode(x=alt.X("date:T", title=None), y=alt.Y("RSI:Q", scale=alt.Scale(domain=(0, 100)))).properties(height=180), width="stretch")
        with c2:
            st.caption("MACD")
            st.altair_chart(alt.Chart(idf).mark_line(color="#22c55e").encode(x=alt.X("date:T", title=None), y="MACD:Q").properties(height=180), width="stretch")


# ----------------------------- AI Council -----------------------------
with tab_council:
    st.markdown('<div class="section-h">🛡 AI Council · Multi-Agent Decision Panel</div>', unsafe_allow_html=True)
    if not result or result.get("status") != "ok":
        st.info("Select a ticker and press **Analyze** in the sidebar to convene the council.")
    else:
        sig = result["signal"]["signal"]
        score = result["signal"]["score"]
        risk = result["risk"]
        strat = result["strategy"]
        port_risk = (result.get("portfolio_risk") or {}).get("risk_score")
        conf = min(100, int(abs(fnum(score)) / 65 * 100))

        def card(title, verdict, vclass, body):
            st.markdown(
                f'<div class="card"><div class="card-title"><span>{title}</span><span class="verdict {vclass}">{verdict}</span></div>'
                f'<div class="card-body">{body}</div></div>', unsafe_allow_html=True)

        cA, cB = st.columns(2)
        with cA:
            card("Market Intel", REGIME.get(sig, "—"), "v-warn" if sig == "neutral" else ("v-pass" if sig == "bullish" else "v-fail"),
                 f"Regime <b>{REGIME.get(sig)}</b> · conviction <b>{conf}%</b> from composite score {score}.")
            card("Signal Agent", sig.upper(), "v-pass" if sig != "neutral" else "v-warn",
                 f"RSI · MACD · Bollinger · MA blend → <b>{sig}</b> ({score}).")
            card("Strategy Agent", str(strat.get("strategy", "hold")).upper().replace("_", " "), "v-pass" if strat.get("strategy") != "hold" else "v-warn",
                 f"Options route: <b>{str(strat.get('strategy','hold')).replace('_',' ')}</b><br>Contract: <code>{strat.get('option_symbol') or '—'}</code>")
        with cB:
            approved = fnum(risk["risk_score"]) < 45 or result["path"] == "entry"
            card("Risk Gate", "APPROVED" if approved else "DEFENSE", "v-pass" if approved else "v-fail",
                 f"{result['symbol']} risk <b>{risk['level'].upper()} ({risk['risk_score']}/100)</b> · portfolio {port_risk}/100<br>"
                 f"capital-at-risk {risk['components']['capital_at_risk']} · vol {risk['components']['volatility']} · drawdown {risk['components']['drawdown_pct']}")
            bt_ok = fnum(summary.get("oos_sharpe", 0)) > 0
            card("Backtest (OOS)", "VALIDATED" if bt_ok else "WATCH", "v-pass" if bt_ok else "v-warn",
                 f"70/30 out-of-sample · best <code>{summary.get('oos_best_combo','—')}</code> "
                 f"Sharpe <b>{summary.get('oos_sharpe','—')}</b> · maxDD {summary.get('oos_worst_drawdown_pct','—')}% across {summary.get('tickers','—')} tickers.")
            held = result.get("has_symbol_position")
            card("Exit Agent", "MONITORING" if not held else "ACTIVE", "v-warn" if not held else "v-pass",
                 "Take-profit / stop-loss / expiry guard " + ("armed on the open position." if held else "— no position in this symbol yet."))

        st.markdown('<div class="section-h">🧠 Explainability · Why this decision</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="card" style="border-left-color:#60a5fa;"><div class="card-body">{result["explanation"]}</div></div>', unsafe_allow_html=True)


# ----------------------------- Trade Explorer -----------------------------
with tab_trades:
    hist = load_trade_history()
    st.markdown(f'<div class="section-h">🔎 Auditable Trade Explorer · {len(hist)} logged</div>', unsafe_allow_html=True)
    if hist.empty:
        st.info("No trades yet. Execute a trade to populate the audit trail.")
    else:
        hist = hist.copy()
        hist["timestamp"] = pd.to_datetime(hist["timestamp"], errors="coerce")
        hist = hist.sort_values("timestamp", ascending=False)
        cols = [c for c in ["timestamp", "symbol", "side", "strategy", "status"] if c in hist.columns]
        st.dataframe(hist[cols], width="stretch", hide_index=True)
        st.markdown('<div class="section-h">Why this trade?</div>', unsafe_allow_html=True)
        labels = [f"{r['timestamp']:%Y-%m-%d %H:%M} · {r.get('symbol','?')} · {r.get('strategy','?')}" for _, r in hist.iterrows()]
        pick = st.selectbox("Select a trade for its explainability audit", options=list(range(len(labels))), format_func=lambda i: labels[i])
        row = hist.iloc[pick]
        st.markdown(
            f'<div class="card" style="border-left-color:#60a5fa;"><div class="card-title"><span>{row.get("symbol","?")} · {row.get("strategy","?")}</span>'
            f'<span class="verdict v-pass">{str(row.get("status","")).upper()}</span></div>'
            f'<div class="card-body">{row.get("explanation") or "No explanation stored for this trade."}</div></div>',
            unsafe_allow_html=True,
        )


# ----------------------------- Strategy Lab -----------------------------
with tab_lab:
    st.markdown('<div class="section-h">🧪 Strategy Lab · Out-of-Sample Validation</div>', unsafe_allow_html=True)
    m = st.columns(4)
    kpi(m[0], "OOS Best Combo", str(summary.get("oos_best_combo", "—")).upper())
    kpi(m[1], "OOS Sharpe", f"{summary.get('oos_sharpe', '—')}", "70/30 split", "#34d399" if fnum(summary.get("oos_sharpe", 0)) > 0 else "#f59e0b")
    kpi(m[2], "OOS Max DD", f"{summary.get('oos_worst_drawdown_pct', '—')}%")
    kpi(m[3], "Universe", f"{summary.get('tickers', '—')} tickers")
    st.caption("Every indicator combination is validated on unseen data (last 30%). See demo/backtest_results.md for the full ranking.")

    st.markdown("---")
    st.markdown('<div class="section-h">📡 Live Watchlist Scan</div>', unsafe_allow_html=True)
    if st.button("Scan watchlist now", key="scan_btn"):
        with st.spinner("Scanning…"):
            st.session_state["scan"] = st.session_state.orchestrator.scan_watchlist(WATCHLIST)
    scanned = st.session_state.get("scan")
    if scanned:
        sdf = pd.DataFrame([
            {"symbol": r.get("symbol"), "signal": r.get("signal"), "score": r.get("score"),
             "strategy": r.get("strategy"), "risk": r.get("risk"), "risk level": r.get("risk_level") or "—"}
            for r in scanned
        ])
        try:
            styled = sdf.style.map(lambda v: {"bullish": "color:#34d399", "bearish": "color:#f87171", "neutral": "color:#fbbf24"}.get(v, "color:#94a3b8"), subset=["signal"])
        except AttributeError:
            styled = sdf
        st.dataframe(styled, width="stretch", hide_index=True)
        actionable = [r for r in scanned if r.get("strategy") not in ("hold", None)]
        st.caption(f"{len(actionable)} actionable signal(s) of {len(scanned)} scanned.")
    else:
        st.info("Press **Scan watchlist now** for signals across all 20 tickers.")


# ----------------------------- Portfolio -----------------------------
with tab_port:
    st.markdown('<div class="section-h">💼 Open Positions</div>', unsafe_allow_html=True)
    if not positions:
        st.info("No open positions.")
    else:
        pdf = positions_dataframe(positions)
        fmt = {"Avg Entry": "${:,.2f}", "Current": "${:,.2f}", "Mkt Value": "${:,.2f}", "Unreal P/L": "${:,.2f}", "P/L %": "{:.2f}%", "Qty": "{:.0f}"}
        try:
            styled = pdf.style.map(lambda v: "color:#34d399" if v > 0 else ("color:#f87171" if v < 0 else ""), subset=["Unreal P/L", "P/L %"]).format(fmt)
        except AttributeError:
            styled = pdf
        st.dataframe(styled, width="stretch", hide_index=True)
        st.caption(f"{len(positions)} position(s) · total unrealized P/L ${open_pl:,.2f}")

    st.markdown("---")
    st.markdown('<div class="section-h">🛡 Defense Cycle Result</div>', unsafe_allow_html=True)
    st.caption("Use the sidebar **Defense cycle** button to take-profit / stop-loss / exit near expiry.")
    defense = st.session_state.get("defense")
    if defense:
        st.write(f"Reviewed **{defense.get('evaluated', 0)}** positions · closing **{defense.get('to_close', 0)}**.")
        acts = defense.get("actions", [])
        if acts:
            st.dataframe(pd.DataFrame([
                {"symbol": a["symbol"], "action": a["action"],
                 "P/L %": None if a.get("unrealized_plpc") is None else round(a["unrealized_plpc"] * 100, 1),
                 "days to expiry": a.get("days_to_expiry"), "reason": a["reason"]}
                for a in acts
            ]), width="stretch", hide_index=True)
        else:
            st.success("No position breached take-profit, stop-loss, or the expiry window.")

st.markdown("---")
st.caption("Paper trading only · options positioning, risk defense, and explainable execution. Not investment advice.")
