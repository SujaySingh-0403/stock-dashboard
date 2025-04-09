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


# ========== TAB 1: INDEX TREND (LIVE NSE DATA) ==========
with tab1:
    st.subheader("📊 Live Index Trend (from NSE)")

    index_map = {
        "NIFTY 50": "NIFTY",
        "BANKNIFTY": "BANKNIFTY",
        "FINNIFTY": "FINNIFTY",
        "MIDCAP": "NIFTY MIDCAP 100",
        "SENSEX": "SENSEX"
    }

    index_choice = st.selectbox("Select Index", list(index_map.keys()))
    index_symbol = index_map[index_choice]

    def get_nse_index_data(index_symbol="NIFTY"):
        import requests

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/",
            "Connection": "keep-alive",
        }

        session = requests.Session()
        session.headers.update(headers)

        # First hit to get cookies
        session.get("https://www.nseindia.com")

        url = f"https://www.nseindia.com/api/equity-stockIndices?index={index_symbol}"
        response = session.get(url, timeout=10)

        if response.status_code != 200:
            raise Exception(f"Error: {response.status_code} from NSE")

        data = response.json()
        return data.get("data")[0] if "data" in data and data["data"] else {}

    try:
        index_data = get_nse_index_data(index_symbol)

        st.markdown(f"### 📈 {index_choice} – Live Snapshot")
        c1, c2, c3 = st.columns(3)
        c1.metric("Price", f"₹{index_data['lastPrice']}")
        c2.metric("Change", f"{index_data['change']} ({index_data['percentChange']}%)")
        c3.metric("Volume", f"{index_data['totalTradedVolume']:,}")

        st.markdown("#### 📌 Additional Stats")
        st.write(f"🔺 Day High: ₹{index_data['dayHigh']}")
        st.write(f"🔻 Day Low: ₹{index_data['dayLow']}")
        st.write(f"📏 52-Week High: ₹{index_data['yearHigh']}")
        st.write(f"📉 52-Week Low: ₹{index_data['yearLow']}")
        st.write(f"📊 PE Ratio: {index_data.get('pe', 'N/A')} | PB Ratio: {index_data.get('pb', 'N/A')}")
        st.write(f"💰 Dividend Yield: {index_data.get('divYield', 'N/A')}")

    except Exception as e:
        st.error(f"❌ Failed to fetch NSE Index data: {e}")



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
# ========== TAB 3: F&O OVERVIEW (NSE Live Data) ==========
with tab3:
    st.subheader("📘 Live F&O Futures Overview (via NSE)")

    symbol_input = st.selectbox("Select Symbol", ["NIFTY", "BANKNIFTY", "RELIANCE", "TCS", "SBIN"])

    def get_nse_futures_data(symbol="NIFTY"):
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.nseindia.com",
        }
        session = requests.Session()
        session.headers.update(headers)
        session.get("https://www.nseindia.com")  # Set cookies

        url = f"https://www.nseindia.com/api/quote-derivative?symbol={symbol.upper()}"
        res = session.get(url)
        data = res.json()

        fut_data = None
        for item in data['stocks']:
            if item['metadata']['instrumentType'] in ["FUTIDX", "FUTSTK"]:
                fut_data = item['metadata']
                break

        return {
            "symbol": symbol.upper(),
            "expiry": fut_data.get("expiryDate"),
            "price": fut_data.get("lastPrice"),
            "change": fut_data.get("change"),
            "changePercent": fut_data.get("pChange"),
            "volume": fut_data.get("numberOfContractsTraded"),
            "openInterest": fut_data.get("openInterest")
        } if fut_data else {}

    try:
        fut_info = get_nse_futures_data(symbol_input)
        st.markdown(f"### 🔍 {fut_info['symbol']} Futures Snapshot – Expiry: {fut_info['expiry']}")
        col1, col2, col3 = st.columns(3)
        col1.metric("LTP", f"₹{fut_info['price']}")
        col2.metric("Change %", f"{fut_info['changePercent']}%")
        col3.metric("Open Interest", f"{fut_info['openInterest']}")
        st.write(f"📦 Volume Traded: `{fut_info['volume']}`")
    except Exception as e:
        st.error(f"❌ Failed to fetch NSE Futures data: {e}")

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
