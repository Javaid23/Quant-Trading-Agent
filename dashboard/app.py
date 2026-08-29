import streamlit as st

from agent.orchestrator import Orchestrator


st.set_page_config(page_title="Quant Trading Agent", layout="wide")
st.title("Quant Trading Agent")
st.caption("Paper-trading options signal and risk monitor")

if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = Orchestrator()

symbol = st.text_input("Ticker", value="AAPL").upper()

if st.button("Analyze"):
    try:
        result = st.session_state.orchestrator.evaluate_symbol(symbol)
        st.subheader(f"{symbol} overview")
        st.json({
            "signal": result["signal"],
            "risk": result["risk"],
            "strategy": result["strategy"],
            "explanation": result["explanation"],
        })
    except Exception as exc:
        st.error(f"Analysis failed: {exc}")

st.markdown("---")
st.write("This dashboard shows the current signal, risk posture, and recommended execution strategy for the selected symbol.")
