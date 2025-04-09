import streamlit as st
import pandas as pd
import yfinance as yf
import ta
import plotly.graph_objects as go
from datetime import datetime

# ========== CONFIG ==========
st.set_page_config(page_title="📊 Advanced Indian Stock Dashboard", layout="wide")

# ========== INDEX DROPDOWN ==========
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

st.title("📊 Indian Stock Market Dashboard with Indicators & Tools")
selected_index_name = st.selectbox("Select Index", list(indices.keys()))
selected_index_symbol = indices[selected_index_name]

# ========== STOCK INPUT ==========
stocks = st.text_input("Enter comma-separated NSE Stock Symbols", "RELIANCE, TCS, INFY")
symbols = [s.strip().upper() for s in stocks.split(',')]

# ========== OPTIONS ==========
col1, col2 = st.columns(2)
with col1:
    period = st.selectbox("Select Period", ["1mo", "3mo", "6mo", "1y", "2y"], index=1)
with col2:
    interval = st.selectbox("Select Interval", ["1d", "1h", "15m"], index=0)

# ========== FETCH DATA ==========
@st.cache_data(ttl=300)
def fetch_data(symbol, period, interval):
    ticker = yf.Ticker(f"{symbol}.NS")
    return ticker.history(period=period, interval=interval)

def add_indicators(df):
    df['SMA_20'] = ta.trend.sma_indicator(df['Close'], window=20)
    df['EMA_20'] = ta.trend.ema_indicator(df['Close'], window=20)
    df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
    df['MACD'] = ta.trend.macd_diff(df['Close'])
    bb = ta.volatility.BollingerBands(df['Close'])
    df['BB_High'] = bb.bollinger_hband()
    df['BB_Low'] = bb.bollinger_lband()
    return df

# ========== DISPLAY INDEX ==========
with st.expander(f"📈 {selected_index_name} Trend"):
    index_data = fetch_data(selected_index_symbol, period="3mo", interval="1d")
    st.line_chart(index_data['Close'])

# ========== MAIN LOOP ==========
for symbol in symbols:
    st.subheader(f"📌 {symbol} – Technical Analysis")
    try:
        df = fetch_data(symbol, period, interval)
        if df.empty:
            st.warning(f"No data for {symbol}")
            continue

        df = add_indicators(df)

        latest = df.iloc[-1]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Current Price", f"₹{latest['Close']:.2f}")
        col2.metric("Day High", f"₹{latest['High']:.2f}")
        col3.metric("Day Low", f"₹{latest['Low']:.2f}")
        col4.metric("Volume", f"{latest['Volume']:,}")

        # ========== CANDLESTICK ==========
        st.markdown("### 🕯️ Candlestick Chart with Bollinger Bands")
        fig = go.Figure(data=[
            go.Candlestick(
                x=df.index,
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                name="Price"
            ),
            go.Scatter(x=df.index, y=df['BB_High'], line=dict(color='blue', width=1), name='BB High'),
            go.Scatter(x=df.index, y=df['BB_Low'], line=dict(color='blue', width=1), name='BB Low')
        ])
        st.plotly_chart(fig, use_container_width=True)

        # ========== PRICE + MA ==========
        st.line_chart(df[['Close', 'SMA_20', 'EMA_20']].dropna())

        # ========== RSI ==========
        st.markdown("### ⚡ RSI (Relative Strength Index)")
        st.line_chart(df[['RSI']].dropna())

        # ========== MACD ==========
        st.markdown("### ⚙️ MACD (Moving Average Convergence Divergence)")
        st.line_chart(df[['MACD']].dropna())

        # ========== DOWNLOAD ==========
        csv = df.to_csv().encode('utf-8')
        st.download_button("📥 Download CSV", csv, file_name=f"{symbol}_data.csv", mime='text/csv')

        # ========== ALERT PLACEHOLDER ==========
        st.info("🔔 Alerts coming soon: Set price/indicator-based email/Telegram alerts.")

    except Exception as e:
        st.error(f"Error loading data for {symbol}: {e}")

# ========== AUTO REFRESH ==========
st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} – Auto refresh every 5 minutes.")
