# === stock_dashboard.py ===

import streamlit as st
import pandas as pd
import yfinance as yf
import ta
import plotly.graph_objects as go
import requests
import time
from datetime import datetime
from bs4 import BeautifulSoup

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

# === TAB 1: INDEX TREND ===
with tab1:
    st.title("📊 Indian Stock Market Dashboard")
    selected_index_name = st.selectbox("Select Index", list(indices.keys()))
    selected_index_symbol = indices[selected_index_name]
    index_data = yf.Ticker(selected_index_symbol).history(period="3mo", interval="1d")
    st.subheader(f"{selected_index_name} Trend")
    st.line_chart(index_data["Close"])

# === UTILS ===
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

# === TAB 2: WATCHLIST ===
with tab2:
    st.subheader("📈 Stock Watchlist")

    stocks = st.text_input("Enter comma-separated NSE Stock Symbols", "RELIANCE, TCS, INFY")
    symbols = [s.strip().upper() for s in stocks.split(",")]

    col1, col2 = st.columns(2)
    with col1:
        period = st.selectbox("Select Period", ["1mo", "3mo", "6mo", "1y"], index=1)
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

            st.markdown("#### 🕯️ Candlestick with Bollinger Bands")
            fig = go.Figure(data=[
                go.Candlestick(x=df.index, open=df["Open"], high=df["High"],
                               low=df["Low"], close=df["Close"], name="Price"),
                go.Scatter(x=df.index, y=df["BB_High"], line=dict(color="blue", width=1), name="BB High"),
                go.Scatter(x=df.index, y=df["BB_Low"], line=dict(color="blue", width=1), name="BB Low"),
            ])
            st.plotly_chart(fig, use_container_width=True)

            st.line_chart(df[["Close", "SMA_20", "EMA_20"]].dropna())
            st.markdown("##### ⚡ RSI")
            st.line_chart(df[["RSI"]].dropna())
            st.markdown("##### ⚙️ MACD")
            st.line_chart(df[["MACD"]].dropna())

            csv = df.to_csv().encode("utf-8")
            st.download_button("📥 Download CSV", csv, file_name=f"{symbol}_data.csv", mime="text/csv")

        except Exception as e:
            st.error(f"❌ Error loading {symbol}: {e}")

# === TAB 3: F&O OVERVIEW ===
with tab3:
    st.subheader("📘 F&O Option Chain with Live Greeks")

    # List of available indices for F&O
    indices_for_fo = [
        "NIFTY", "BANKNIFTY", "NIFTY IT", "NIFTY FMCG", "NIFTY AUTO", 
        "NIFTY METAL", "NIFTY PHARMA", "SENSEX", "NIFTY FIN SERVICE"
    ]
    
    # Select index from the available list
    symbol = st.selectbox("Select Index", indices_for_fo)
    
    # Source toggle for data (NSE or StockMock)
    data_source = st.radio("Select Data Source", ["NSE", "StockMock"], index=0)

    # Fetch Expiry Dates based on symbol and source
    @st.cache_data(ttl=300)
    def fetch_expiry_dates(symbol, source):
        if source == "NSE":
            url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
            headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
            res = requests.get(url, headers=headers)
            if res.status_code == 200:
                return res.json()["records"]["expiryDates"]
        elif source == "StockMock":
            url = f"https://www.stockmock.in/option-chain/{symbol}"
            res = requests.get(url)
            if res.status_code == 200:
                soup = BeautifulSoup(res.content, "html.parser")
                return [opt.text for opt in soup.find_all("option", {"class": "expiry-dates"})]
        return []

    # Get expiry dates
    expiry_dates = fetch_expiry_dates(symbol, data_source)
    expiry = st.selectbox("Select Expiry Date", expiry_dates)

    # Fetch Option Chain data based on selected symbol, expiry, and source
    @st.cache_data(ttl=300)
    def fetch_option_chain(symbol, expiry, source):
        if source == "NSE":
            url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
            headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
            res = requests.get(url, headers=headers)
            if res.status_code == 200:
                data = res.json()["records"]["data"]
                chain = []
                for d in data:
                    if d["expiryDate"] == expiry:
                        strike = d["strikePrice"]
                        ce = d.get("CE", {})
                        pe = d.get("PE", {})
                        chain.append({
                            "Strike": strike,
                            "CE_LTP": ce.get("lastPrice"), "CE_IV": ce.get("impliedVolatility"),
                            "CE_OI": ce.get("openInterest"), "CE_Change_OI": ce.get("changeinOpenInterest"),
                            "PE_LTP": pe.get("lastPrice"), "PE_IV": pe.get("impliedVolatility"),
                            "PE_OI": pe.get("openInterest"), "PE_Change_OI": pe.get("changeinOpenInterest")
                        })
                return pd.DataFrame(chain)
        elif source == "StockMock":
            url = f"https://www.stockmock.in/option-chain/{symbol}/{expiry}"
            res = requests.get(url)
            if res.status_code == 200:
                soup = BeautifulSoup(res.content, "html.parser")
                table = soup.find("table", {"id": "option-chain-table"})
                return pd.read_html(str(table))[0]
        return pd.DataFrame()

    # Fetch the option chain data
    option_chain = fetch_option_chain(symbol, expiry, data_source)
    
    if not option_chain.empty:
        st.success("✅ Option Chain Loaded")
        
        try:
            spot = option_chain["Strike"].iloc[(option_chain["Strike"] - option_chain["CE_LTP"]).abs().argsort()[:1]].values[0]
        except:
            spot = option_chain["Strike"].median()
        
        strike_range = st.slider("ATM ± Strikes", 1, 10, 5)
        filtered = option_chain[(option_chain["Strike"] >= spot - strike_range*50) & (option_chain["Strike"] <= spot + strike_range*50)]
        
        def highlight(val, col):
            if col in ["CE_IV", "PE_IV"] and isinstance(val, (int, float)) and val > 30:
                return 'background-color: yellow'
            if col == "Strike" and val == spot:
                return 'background-color: lightblue'
            return ''

        st.dataframe(
            filtered.style.applymap(lambda val: highlight(val, "CE_IV"), subset=["CE_IV"])
                            .applymap(lambda val: highlight(val, "PE_IV"), subset=["PE_IV"])
                            .applymap(lambda val: highlight(val, "Strike"), subset=["Strike"]),
            use_container_width=True
        )

    st.caption(f"Data Source: {data_source} | Last Refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

