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

def add_indicators(df, rsi_period, macd_fast, macd_slow, macd_signal, ma_window, bb_window, bb_std):
    df["SMA"] = ta.trend.sma_indicator(df["Close"], window=ma_window)
    df["EMA"] = ta.trend.ema_indicator(df["Close"], window=ma_window)
    df["RSI"] = ta.momentum.rsi(df["Close"], window=rsi_period)
    macd = ta.trend.macd(df["Close"], window_fast=macd_fast, window_slow=macd_slow, window_sign=macd_signal)
    df["MACD"] = macd - ta.trend.macd_signal(df["Close"], window_fast=macd_fast, window_slow=macd_slow, window_sign=macd_signal)
    bb = ta.volatility.BollingerBands(df["Close"], window=bb_window, window_dev=bb_std)
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

    st.markdown("### 🎛️ Indicator Settings")

    show_rsi = st.checkbox("📉 Show RSI", value=True)
    rsi_period = st.slider("RSI Period", 5, 30, 14)

    show_macd = st.checkbox("📊 Show MACD", value=True)
    macd_fast = st.slider("MACD Fast Period", 5, 20, 12)
    macd_slow = st.slider("MACD Slow Period", 10, 30, 26)
    macd_signal = st.slider("MACD Signal Period", 5, 15, 9)

    show_bb = st.checkbox("📦 Show Bollinger Bands", value=True)
    bb_window = st.slider("BB Window", 10, 30, 20)
    bb_std = st.slider("BB Std Dev", 1, 3, 2)

    show_ma = st.checkbox("🧮 Show SMA & EMA", value=True)
    ma_window = st.slider("MA Window", 10, 50, 20)

    for symbol in symbols:
        st.markdown(f"---\n### 📌 {symbol} – Technical Overview")
        try:
            df = fetch_data(symbol, period, interval)
            if df.empty:
                st.warning(f"No data for {symbol}")
                continue
            df = add_indicators(df, rsi_period, macd_fast, macd_slow, macd_signal, ma_window, bb_window, bb_std)
            latest = df.iloc[-1]

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Current Price", f"₹{latest['Close']:.2f}")
            c2.metric("Day High", f"₹{latest['High']:.2f}")
            c3.metric("Day Low", f"₹{latest['Low']:.2f}")
            c4.metric("Volume", f"{latest['Volume']:,}")

            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=df.index, open=df["Open"], high=df["High"],
                low=df["Low"], close=df["Close"], name="Candlestick"
            ))

            if show_bb:
                fig.add_trace(go.Scatter(x=df.index, y=df["BB_High"], name="BB High",
                                         line=dict(color="blue", width=1)))
                fig.add_trace(go.Scatter(x=df.index, y=df["BB_Low"], name="BB Low",
                                         line=dict(color="blue", width=1)))
            if show_ma:
                fig.add_trace(go.Scatter(x=df.index, y=df["SMA"], name="SMA",
                                         line=dict(color="orange")))
                fig.add_trace(go.Scatter(x=df.index, y=df["EMA"], name="EMA",
                                         line=dict(color="green")))
            fig.update_layout(title=f"{symbol} - Price with Indicators", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            if show_rsi:
                st.markdown("##### ⚡ RSI")
                st.line_chart(df[["RSI"]])

            if show_macd:
                st.markdown("##### ⚙️ MACD")
                st.line_chart(df[["MACD"]])

            csv = df.to_csv().encode("utf-8")
            st.download_button("📥 Download CSV", csv, file_name=f"{symbol}_data.csv", mime="text/csv")

        except Exception as e:
            st.error(f"❌ Error loading {symbol}: {e}")

# === TAB 3: F&O Option Chain with Source Toggle ===
with tab3:
    st.header("📘 F&O Option Chain")

    fo_symbol = st.text_input("Enter F&O Symbol (e.g. NIFTY, BANKNIFTY)", "NIFTY")
    source_toggle = st.radio("Select Data Source", ["StockMock", "NSE"], horizontal=True)

    def fetch_stockmock_option_chain(symbol):
        url = f"https://www.stockmock.in/option-chain/{symbol.upper()}"
        try:
            res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(res.text, "html.parser")
            tables = soup.find_all("table")
            if tables:
                return pd.read_html(str(tables[0]))[0]
        except:
            return None

    def fetch_nse_option_chain(symbol):
        try:
            url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol.upper()}"
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.nseindia.com"
            }
            session = requests.Session()
            session.get("https://www.nseindia.com", headers=headers)
            response = session.get(url, headers=headers)
            data = response.json()
            return pd.json_normalize(data["records"]["data"])
        except:
            return None

    if fo_symbol:
        if source_toggle == "StockMock":
            st.subheader(f"StockMock Option Chain for {fo_symbol}")
            stockmock_data = fetch_stockmock_option_chain(fo_symbol)
            if stockmock_data is not None:
                st.dataframe(stockmock_data)
            else:
                st.warning("⚠️ Could not fetch data from StockMock.")
        else:
            st.subheader(f"NSE Option Chain for {fo_symbol}")
            nse_data = fetch_nse_option_chain(fo_symbol)
            if nse_data is not None:
                st.dataframe(nse_data)
            else:
                st.warning("⚠️ Could not fetch data from NSE.")
