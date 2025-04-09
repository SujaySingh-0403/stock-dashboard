import streamlit as st
import pandas as pd
import requests
import yfinance as yf
import ta
import plotly.graph_objects as go
import time
from datetime import datetime
from bs4 import BeautifulSoup
from typing import List

# ========== CONFIG ==========
st.set_page_config(page_title="📊 Indian Stock Market Dashboard", layout="wide")

# ========== HEADERS FOR NSE SCRAPING ==========
def nse_headers():
    return {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/"
    }

# ========== NSE OPTION CHAIN FETCH ==========
@st.cache_data(ttl=300)
def fetch_option_chain(symbol: str):
    session = requests.Session()
    base_url = "https://www.nseindia.com"

    # Determine endpoint
    if symbol.upper() in ["NIFTY", "BANKNIFTY"]:
        url = f"{base_url}/api/option-chain-indices?symbol={symbol.upper()}"
    else:
        url = f"{base_url}/api/option-chain-equities?symbol={symbol.upper()}"

    try:
        # Preload cookies
        session.get(base_url, headers=nse_headers(), timeout=5)
        response = session.get(url, headers=nse_headers(), timeout=5)
        data = response.json()
        records = data["records"]
        expiry_dates = records["expiryDates"]
        underlying = records["underlyingValue"]
        df = pd.json_normalize(records["data"], sep="_")
        return df, expiry_dates, underlying
    except Exception as e:
        st.error(f"Error fetching option chain: {e}")
        return pd.DataFrame(), [], 0

# ========== SIDEBAR ==========
st.sidebar.header("🔧 Controls")

enable_auto = st.sidebar.checkbox("🔄 Enable Auto Refresh", value=False)
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
    "SENSEX": "^BSESN"
}

# ========== MAIN TABS ==========
tab1, tab2, tab3 = st.tabs(["📊 Index Trend", "📈 Watchlist", "📘 F&O Overview"])

# ========== INDEX TREND TAB ==========
with tab1:
    st.title("📊 Indian Stock Market Dashboard")
    selected_index_name = st.selectbox("Select Index", list(indices.keys()))
    selected_index_symbol = indices[selected_index_name]
    index_data = yf.Ticker(selected_index_symbol).history(period="3mo", interval="1d")
    st.subheader(f"{selected_index_name} Trend")
    st.line_chart(index_data["Close"])

# ========== WATCHLIST UTILS ==========
@st.cache_data(ttl=300)
def fetch_data(symbol, period, interval):
    ticker = yf.Ticker(f"{symbol}.NS")
    return ticker.history(period=period, interval=interval)

@st.cache_data(ttl=300)
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

            if latest['RSI'] > 70:
                st.warning(f"🚨 RSI Overbought: {latest['RSI']:.2f}")
            elif latest['RSI'] < 30:
                st.success(f"📉 RSI Oversold: {latest['RSI']:.2f}")

            st.line_chart(df[["Close", "SMA_20", "EMA_20"]].dropna())
            st.line_chart(df[["RSI"]].dropna())
            st.line_chart(df[["MACD"]].dropna())

        except Exception as e:
            st.error(f"❌ Error loading {symbol}: {e}")

# ========== F&O OVERVIEW TAB ==========
with tab3:
    st.subheader("📘 F&O Option Chain with Live Greeks")

    symbol = st.text_input("Enter Symbol (e.g. NIFTY, BANKNIFTY, RELIANCE)", "NIFTY")
    df, expiries, underlying = fetch_option_chain(symbol.upper())

    if not df.empty:
        expiry = st.selectbox("Select Expiry Date", expiries)
        atm_range = st.slider("ATM ± Strikes", 2, 20, 10)

        df = df[df["expiryDate"] == expiry]
        df = df.sort_values("strikePrice")
        atm_strike = df.iloc[(df["strikePrice"] - underlying).abs().argsort()].iloc[0]["strikePrice"]
        min_strike = atm_strike - atm_range * 50
        max_strike = atm_strike + atm_range * 50
        df_filtered = df[(df["strikePrice"] >= min_strike) & (df["strikePrice"] <= max_strike)]

        st.write(f"Underlying: {underlying} | ATM Strike: {atm_strike}")

        oc_table = pd.DataFrame({
            "Strike": df_filtered["strikePrice"],
            "CE LTP": df_filtered["CE_lastPrice"].fillna("-"),
            "CE IV": df_filtered["CE_impliedVolatility"].fillna("-"),
            "CE OI": df_filtered["CE_openInterest"].fillna("-"),
            "PE LTP": df_filtered["PE_lastPrice"].fillna("-"),
            "PE IV": df_filtered["PE_impliedVolatility"].fillna("-"),
            "PE OI": df_filtered["PE_openInterest"].fillna("-"),
        })
        st.dataframe(oc_table, use_container_width=True)

# ========== FOOTER ==========
st.markdown("---")
st.caption(f"⏱️ Last Refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
