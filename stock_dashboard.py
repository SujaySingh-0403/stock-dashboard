import streamlit as st
import pandas as pd
import yfinance as yf
import ta
import plotly.graph_objects as go
import time
from datetime import datetime

# ========== CONFIG ==========
st.set_page_config(page_title="📊 Indian Stock Market Dashboard", layout="wide")

# ========== SIDEBAR SETTINGS ==========
st.sidebar.header("🔧 Controls")

enable_auto = st.sidebar.checkbox("🔄 Enable Auto Refresh", value=True)
refresh_interval = st.sidebar.slider("⏱️ Refresh Interval (sec)", 30, 600, 300, step=30)

if st.sidebar.button("🔁 Manual Refresh"):
    st.rerun()

if enable_auto:
    time.sleep(refresh_interval)
    st.rerun()

# ========== INDEX DATA ==========
indices = {
    "NIFTY 50": "^NSEI",
    "NIFTY BANK": "^NSEBANK",
    "NIFTY IT": "^CNXIT",
    "NIFTY FMCG": "^CNXFMCG",
    "NIFTY AUTO": "^CNXAUTO",
    "NIFTY METAL": "^CNXMETAL",
    "NIFTY PHARMA": "^CNXPHARMA",
    "SENSEX": "^BSESN"
}

# ========== MAIN UI ==========
tab1, tab2, tab3 = st.tabs(["📊 Index Trend", "📈 Watchlist", "📘 F&O Overview"])

# ========== INDEX TAB ==========
with tab1:
    st.title("📊 Indian Stock Market Dashboard")
    selected_index_name = st.selectbox("Select Index", list(indices.keys()))
    selected_index_symbol = indices[selected_index_name]

    index_data = yf.Ticker(selected_index_symbol).history(period="3mo", interval="1d")
    st.subheader(f"{selected_index_name} Trend")
    st.line_chart(index_data["Close"])

# ========== FETCH UTILS ==========
@st.cache_data(ttl=300)
def fetch_data(symbol, period, interval):
    ticker = yf.Ticker(f"{symbol}.NS")
    return ticker.history(period=period, interval=interval)

def add_indicators(df):
    df["SMA_20"] = ta.trend.sma_indicator(df["Close"], window=20)
    df["EMA_20"] = ta.trend.ema_indicator(df["Close"], window=20)
    df["RSI"] = ta.momentum.rsi(df["Close"], window=14)
    df["MACD"] = ta.trend.macd_diff(df["Close"])
    bb = ta.volatility.BollingerBands(df["Close"])
    df["BB_High"] = bb.bollinger_hband()
    df["BB_Low"] = bb.bollinger_lband()
    return df

# ========== WATCHLIST TAB ==========
with tab2:
    st.subheader("📈 Stock Watchlist")

    stocks = st.text_input("Enter comma-separated NSE Stock Symbols", "RELIANCE, TCS, INFY")
    symbols = [s.strip().upper() for s in stocks.split(",")]

    col1, col2 = st.columns(2)
    with col1:
        period = st.selectbox("Select Period", ["1mo", "3mo", "6mo", "1y", "2y"], index=1)
    with col2:
        interval = st.selectbox("Select Interval", ["1d", "1h", "15m"], index=0)

    for symbol in symbols:
        st.markdown(f"---\n### 📌 {symbol} – Technical Overview")
        try:
            df = fetch_data(symbol, period, interval)
            if df.empty:
                st.warning(f"No data for {symbol}")
                continue

            df = add_indicators(df)
            latest = df.iloc[-1]

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Current Price", f"₹{latest['Close']:.2f}")
            c2.metric("Day High", f"₹{latest['High']:.2f}")
            c3.metric("Day Low", f"₹{latest['Low']:.2f}")
            c4.metric("Volume", f"{latest['Volume']:,}")

            # Alerts
            if latest['RSI'] > 70:
                st.warning(f"🚨 RSI Overbought: {latest['RSI']:.2f}")
            elif latest['RSI'] < 30:
                st.success(f"📉 RSI Oversold: {latest['RSI']:.2f}")

            if latest["MACD"] > 0 and df["MACD"].iloc[-2] < 0:
                st.info("📈 MACD Bullish Crossover Detected")
            elif latest["MACD"] < 0 and df["MACD"].iloc[-2] > 0:
                st.error("📉 MACD Bearish Crossover Detected")

            # Candlestick + Bollinger
            st.markdown("#### 🕯️ Candlestick with Bollinger Bands")
            fig = go.Figure(data=[
                go.Candlestick(
                    x=df.index, open=df["Open"], high=df["High"],
                    low=df["Low"], close=df["Close"], name="Price"
                ),
                go.Scatter(x=df.index, y=df["BB_High"], line=dict(color="blue", width=1), name="BB High"),
                go.Scatter(x=df.index, y=df["BB_Low"], line=dict(color="blue", width=1), name="BB Low"),
            ])
            st.plotly_chart(fig, use_container_width=True)

            # Price + MA
            st.line_chart(df[["Close", "SMA_20", "EMA_20"]].dropna())
            st.markdown("##### ⚡ RSI")
            st.line_chart(df[["RSI"]].dropna())
            st.markdown("##### ⚙️ MACD")
            st.line_chart(df[["MACD"]].dropna())

            # Download
            csv = df.to_csv().encode("utf-8")
            st.download_button("📥 Download CSV", csv, file_name=f"{symbol}_data.csv", mime="text/csv")

        except Exception as e:
            st.error(f"❌ Error loading {symbol}: {e}")

# ========== F&O OVERVIEW TAB ==========
with tab3:
    st.subheader("📘 F&O Data (Coming Soon)")
    st.info("Option Chain, IV, OI Analysis, Strategy Builder – under development.")

# ========== FOOTER ==========
st.markdown("---")
st.caption(f"⏱️ Last Refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
