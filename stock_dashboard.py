import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta
import numpy as np
import math

st.set_page_config(page_title="📈 Stock Market Dashboard", layout="wide")
st.title("📊 Live Indian Stock Market Dashboard")

# ----------- Sidebar Options -----------
st.sidebar.header("⚙️ Dashboard Settings")

indices = {
    "NIFTY 50": "^NSEI",
    "BANK NIFTY": "^NSEBANK",
    "NIFTY IT": "^CNXIT",
    "NIFTY FMCG": "^CNXFMCG",
    "NIFTY PHARMA": "^CNXPHARMA",
    "NIFTY AUTO": "^CNXAUTO"
}

selected_index = st.sidebar.selectbox("📌 Select Index", list(indices.keys()))

watchlist = st.sidebar.text_input("📃 Enter comma-separated stock symbols (NSE)", "RELIANCE.NS, TCS.NS")

period = st.sidebar.selectbox("📆 Data Period", ["1d", "5d", "1mo", "3mo", "6mo", "1y"], index=2)
interval = st.sidebar.selectbox("⏱️ Interval", ["1m", "5m", "15m", "30m", "1h", "1d"], index=4)
refresh_sec = st.sidebar.slider("🔄 Auto Refresh (seconds)", 0, 300, 0, step=10)
if refresh_sec > 0:
    st.experimental_rerun()

# ----------- Tabs -----------
tab1, tab2, tab3 = st.tabs(["📈 Index Overview", "📊 Stock Watchlist", "📘 F&O Overview"])

# ----------- Helper Functions -----------
@st.cache_data(ttl=300)
def fetch_data(symbol, period, interval):
    df = yf.download(symbol, period=period, interval=interval, progress=False)
    df.dropna(inplace=True)
    return df

@st.cache_data(ttl=300)
def add_indicators(df):
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['Upper'] = df['MA20'] + 2 * df['Close'].rolling(window=20).std()
    df['Lower'] = df['MA20'] - 2 * df['Close'].rolling(window=20).std()
    return df

@st.cache_data(ttl=300)
def fetch_option_chain(symbol="NIFTY"):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br"
    }
    url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
    session = requests.Session()
    session.get("https://www.nseindia.com", headers=headers)
    response = session.get(url, headers=headers)
    data = response.json()
    return data

def calculate_greeks(S, K, T, r, sigma, option_type="call"):
    d1 = (np.log(S/K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if option_type == "call":
        delta = math.erf(d1 / math.sqrt(2))
    else:
        delta = -math.erf(-d1 / math.sqrt(2))
    gamma = np.exp(-d1 ** 2 / 2) / (S * sigma * np.sqrt(2 * math.pi * T))
    return round(delta, 4), round(gamma, 4)

# ----------- INDEX TAB -----------
with tab1:
    st.subheader(f"📌 {selected_index} Overview")
    index_symbol = indices[selected_index]
    df_index = fetch_data(index_symbol, period, interval)
    df_index = add_indicators(df_index)

    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df_index.index, open=df_index['Open'], high=df_index['High'],
                                 low=df_index['Low'], close=df_index['Close'], name='Price'))
    fig.add_trace(go.Scatter(x=df_index.index, y=df_index['MA20'], line=dict(color='blue', width=1), name='MA20'))
    fig.add_trace(go.Scatter(x=df_index.index, y=df_index['Upper'], line=dict(color='gray', width=1), name='Upper BB'))
    fig.add_trace(go.Scatter(x=df_index.index, y=df_index['Lower'], line=dict(color='gray', width=1), name='Lower BB'))
    fig.update_layout(height=500, margin=dict(l=20, r=20, t=30, b=20))

    st.plotly_chart(fig, use_container_width=True)

# ----------- WATCHLIST TAB -----------
with tab2:
    st.subheader("📊 Stock Watchlist")
    symbols = [sym.strip().upper() for sym in watchlist.split(",") if sym.strip()]
    for symbol in symbols:
        st.markdown(f"### {symbol}")
        try:
            df = fetch_data(symbol, period, interval)
            df = add_indicators(df)
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                                         low=df['Low'], close=df['Close'], name='Price'))
            fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='blue', width=1), name='MA20'))
            fig.add_trace(go.Scatter(x=df.index, y=df['Upper'], line=dict(color='gray', width=1), name='Upper BB'))
            fig.add_trace(go.Scatter(x=df.index, y=df['Lower'], line=dict(color='gray', width=1), name='Lower BB'))
            fig.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Failed to load {symbol}: {e}")

# ----------- F&O OVERVIEW TAB -----------
with tab3:
    st.subheader("📘 F&O Option Chain (NIFTY & BANKNIFTY Only)")

    symbol = st.selectbox("Select Symbol", ["NIFTY", "BANKNIFTY"])
    strike_range = st.slider("ATM ± Strikes", 5, 20, 10, step=1)

    try:
        data = fetch_option_chain(symbol)
        records = data["records"]
        expiry_dates = records["expiryDates"]
        atm = records["underlyingValue"]
        st.markdown(f"**Underlying (ATM): ₹{atm:.2f}**")

        expiry = st.selectbox("Select Expiry", expiry_dates)

        ce_data, pe_data = [], []
        for d in records["data"]:
            if d["expiryDate"] != expiry:
                continue
            strike = d["strikePrice"]
            if abs(strike - atm) > strike_range * 50:
                continue
            ce = d.get("CE")
            pe = d.get("PE")
            if ce:
                T = 1/365  # approx 1 day to expiry
                r = 0.05
                sigma = ce.get("impliedVolatility", 0)/100 or 0.3
                delta, gamma = calculate_greeks(atm, strike, T, r, sigma, option_type="call")
                ce_data.append({
                    "Strike": strike,
                    "LTP": ce.get("lastPrice"),
                    "IV": ce.get("impliedVolatility"),
                    "OI": ce.get("openInterest"),
                    "Chng OI": ce.get("changeinOpenInterest"),
                    "Volume": ce.get("totalTradedVolume"),
                    "Delta": delta,
                    "Gamma": gamma
                })
            if pe:
                T = 1/365
                r = 0.05
                sigma = pe.get("impliedVolatility", 0)/100 or 0.3
                delta, gamma = calculate_greeks(atm, strike, T, r, sigma, option_type="put")
                pe_data.append({
                    "Strike": strike,
                    "LTP": pe.get("lastPrice"),
                    "IV": pe.get("impliedVolatility"),
                    "OI": pe.get("openInterest"),
                    "Chng OI": pe.get("changeinOpenInterest"),
                    "Volume": pe.get("totalTradedVolume"),
                    "Delta": delta,
                    "Gamma": gamma
                })

        df_ce = pd.DataFrame(ce_data).set_index("Strike")
        df_pe = pd.DataFrame(pe_data).set_index("Strike")
        df_all = pd.concat([df_ce.add_prefix("CE "), df_pe.add_prefix("PE ")], axis=1).sort_index()

        st.dataframe(df_all.style.background_gradient(cmap="Blues", axis=0), use_container_width=True)

        st.markdown("### 📊 Open Interest by Strike")
        st.bar_chart(df_all[["CE OI", "PE OI"]])

    except Exception as e:
        st.error(f"Error loading option chain: {e}")
