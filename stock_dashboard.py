import streamlit as st
import pandas as pd
import yfinance as yf
import ta
import plotly.graph_objects as go
import time
from datetime import datetime
from bs4 import BeautifulSoup
import requests


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
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Index Trend",
    "📈 Watchlist",
    "📘 F&O Overview",
    "🧮 Option Chain"
])


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
# ========== TAB 3: F&O OVERVIEW ==========
with tab3:
    st.subheader("📘 Futures & Options Overview")

    fut_symbol = st.selectbox("Select Futures Symbol", ["NIFTY", "BANKNIFTY", "RELIANCE", "TCS", "SBIN"])
    ticker = yf.Ticker(f"{fut_symbol}.NS")

    try:
        fut_data = ticker.history(period="2mo", interval="1d")
        fut_data = add_indicators(fut_data)
        latest = fut_data.iloc[-1]

        st.markdown(f"### {fut_symbol} – Futures Snapshot")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Price", f"₹{latest['Close']:.2f}")
        c2.metric("Change", f"{((latest['Close'] - latest['Open']) / latest['Open'] * 100):.2f}%")
        c3.metric("Volume", f"{int(latest['Volume']):,}")
        c4.metric("RSI", f"{latest['RSI']:.2f}")

        st.markdown("#### 📊 Trend Overview")
        st.line_chart(fut_data[["Close", "SMA_20", "EMA_20"]].dropna())
        st.markdown("##### ⚙️ MACD")
        st.line_chart(fut_data[["MACD"]].dropna())

        # Optional Alerts
        if latest['RSI'] > 70:
            st.warning("🔴 Overbought (RSI > 70)")
        elif latest['RSI'] < 30:
            st.success("🟢 Oversold (RSI < 30)")

    except Exception as e:
        st.error(f"Failed to fetch data for {fut_symbol}: {e}")
# ========== TAB 4: OPTION CHAIN WITH GREEKS ==========
with tab4:
    st.subheader("🧮 F&O Option Chain with Greeks – StockMock")

    instrument = st.selectbox("Select Instrument", ["NIFTY", "BANKNIFTY"])
    url = f"https://www.stockmock.in/option-chain/{instrument.lower()}/weekly"

    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")

        # ATM Strike
        atm_tag = soup.find("span", {"class": "atmStrike"})
        atm_strike = int(atm_tag.text.strip()) if atm_tag else 0

        # Option Chain Table
        table = soup.find("table")
        headers = [th.text.strip() for th in table.find("thead").find_all("th")]
        rows = []
        for tr in table.find("tbody").find_all("tr"):
            cells = [td.text.strip().replace(',', '') for td in tr.find_all("td")]
            if len(cells) == len(headers):
                rows.append(dict(zip(headers, cells)))

        df_oc = pd.DataFrame(rows)

        # Convert numeric
        for col in df_oc.columns:
            try:
                df_oc[col] = pd.to_numeric(df_oc[col])
            except:
                pass

        # Filter strikes ±500
        st.markdown(f"📍 ATM Strike: **{atm_strike}**")
        lower, upper = atm_strike - 500, atm_strike + 500
        df_oc = df_oc[(df_oc["Strike"] >= lower) & (df_oc["Strike"] <= upper)]

        # Display table
        st.dataframe(df_oc.style
            .highlight_max(axis=0, color="lightgreen")
            .highlight_min(axis=0, color="salmon"),
            use_container_width=True)

        # Download
        csv_oc = df_oc.to_csv(index=False).encode()
        st.download_button("📥 Download Option Chain CSV", csv_oc, file_name=f"{instrument}_option_chain.csv")

    except Exception as e:
        st.error(f"❌ Failed to fetch Option Chain: {e}")


# ========== FOOTER ==========
st.markdown("---")
st.caption(f"⏱️ Last Refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
