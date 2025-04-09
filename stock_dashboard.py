import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from ta.trend import SMAIndicator, EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
from ta.trend import MACD
from io import StringIO
import plotly.graph_objs as go

st.set_page_config(page_title="📈 Stock Dashboard", layout="wide")

st.title("📊 Indian Stock Market Dashboard")

# === SIDEBAR ===
with st.sidebar:
    st.header("🔁 Auto Refresh")
    refresh_rate = st.slider("Refresh interval (seconds)", 10, 300, 60)
    st.caption("⏱️ Refreshes using browser reload")

# === AUTO REFRESH ===
st.markdown(
    f"""
    <meta http-equiv="refresh" content="{refresh_rate}">
    """,
    unsafe_allow_html=True
)

# === TABS ===
tab1, tab2, tab3 = st.tabs(["📈 Index Overview", "📘 Watchlist + Technicals", "📘 F&O Overview"])

# === TAB 1: INDEX OVERVIEW ===
with tab1:
    st.subheader("📈 Index Overview")
    indices = {
        "NIFTY 50": "^NSEI",
        "BANKNIFTY": "^NSEBANK",
        "SENSEX": "^BSESN",
        "NIFTY IT": "^CNXIT",
        "NIFTY AUTO": "^CNXAUTO",
        "NIFTY FMCG": "^CNXFMCG",
        "NIFTY METAL": "^CNXMETAL",
        "NIFTY PHARMA": "^CNXPHARMA",
        "NIFTY FIN SERVICE": "^CNXFIN",
        "MIDCAP NIFTY": "^NSEMDCP50"
    }

    index_choice = st.selectbox("Select Index", list(indices.keys()))
    index_symbol = indices[index_choice]
    df = yf.download(index_symbol, period="3mo", interval="1d")
    st.line_chart(df['Close'])

# === TAB 2: WATCHLIST + TECHNICALS ===
with tab2:
    st.subheader("📘 Watchlist + Technical Indicators")
    watchlist_input = st.text_input("Enter NSE stock symbols (comma separated)", "RELIANCE, TCS, INFY")
    stocks = [s.strip().upper() for s in watchlist_input.split(",")]

    for stock in stocks:
        st.markdown(f"### {stock}")
        data = yf.download(f"{stock}.NS", period="3mo", interval="1d")
        if not data.empty:
            # Indicators
            data['SMA'] = SMAIndicator(data['Close'], 20).sma_indicator()
            data['EMA'] = EMAIndicator(data['Close'], 20).ema_indicator()
            data['RSI'] = RSIIndicator(data['Close']).rsi()
            bb = BollingerBands(data['Close'])
            data['BB_Upper'] = bb.bollinger_hband()
            data['BB_Lower'] = bb.bollinger_lband()
            macd = MACD(data['Close'])
            data['MACD'] = macd.macd()

            # ✅ FIXED 1D PLOTTING
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=data.index, y=data['Close'], name='Close'))
            fig.add_trace(go.Scatter(x=data.index, y=data['SMA'], name='SMA20'))
            fig.add_trace(go.Scatter(x=data.index, y=data['EMA'], name='EMA20'))
            fig.add_trace(go.Scatter(x=data.index, y=data['BB_Upper'], name='BB Upper', line=dict(dash='dot')))
            fig.add_trace(go.Scatter(x=data.index, y=data['BB_Lower'], name='BB Lower', line=dict(dash='dot')))
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(data[['Close', 'RSI', 'MACD']].dropna().tail(10))
        else:
            st.warning(f"No data for {stock}")

# === TAB 3: F&O OPTION CHAIN ===
with tab3:
    st.subheader("📘 F&O Option Chain with Live Greeks")

    index_choices = [
        "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX",
        "NIFTYIT", "NIFTYAUTO", "NIFTYFMCG", "NIFTYMETAL", "NIFTYPHARMA"
    ]
    symbol = st.selectbox("Select Index Symbol", index_choices)
    data_source = st.radio("Select Data Source", ["NSE", "StockMock"], index=0)

    @st.cache_data(ttl=300)
    def fetch_expiry_dates(symbol, source):
        if source == "NSE":
            try:
                url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
                headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
                res = requests.get(url, headers=headers, timeout=5)
                if res.status_code == 200:
                    return res.json()["records"]["expiryDates"]
            except Exception:
                return []
        elif source == "StockMock":
            try:
                url = f"https://www.stockmock.in/option-chain/{symbol}"
                res = requests.get(url, timeout=5)
                soup = BeautifulSoup(res.content, "html.parser")
                return [opt.text for opt in soup.find_all("option", {"class": "expiry-dates"})]
            except Exception:
                return []
        return []

    expiry_dates = fetch_expiry_dates(symbol, data_source)
    expiry = st.selectbox("Select Expiry Date", expiry_dates) if expiry_dates else "NA"

    @st.cache_data(ttl=300)
    def fetch_option_chain(symbol, expiry, source):
        if source == "NSE":
            try:
                url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
                headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
                res = requests.get(url, headers=headers, timeout=5)
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
            except Exception:
                return pd.DataFrame()
        elif source == "StockMock":
            try:
                url = f"https://www.stockmock.in/option-chain/{symbol}/{expiry}"
                res = requests.get(url)
                soup = BeautifulSoup(res.content, "html.parser")
                table = soup.find("table", {"id": "option-chain-table"})
                return pd.read_html(StringIO(str(table)))[0]  # ✅ FIXED using StringIO
            except Exception:
                return pd.DataFrame()
        return pd.DataFrame()

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
            filtered.style
            .applymap(lambda val: highlight(val, "CE_IV"), subset=["CE_IV"])
            .applymap(lambda val: highlight(val, "PE_IV"), subset=["PE_IV"])
            .applymap(lambda val: highlight(val, "Strike"), subset=["Strike"]),
            use_container_width=True
        )

    st.caption(f"Data Source: {data_source} | Last Refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
