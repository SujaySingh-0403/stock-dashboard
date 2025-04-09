import streamlit as st
import yfinance as yf
import pandas as pd
import requests

st.set_page_config(layout="wide", page_title="📊 Stock Market Dashboard")

# Title
st.title("📊 Live Stock Market Dashboard")

# Tabs
tab1, tab2, tab3 = st.tabs(["📈 Technical Dashboard", "📘 Indices", "💰 F&O Option Chain"])

# Dropdown for stock symbols
stocks = ["RELIANCE.NS", "INFY.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS"]
selected_symbol = st.sidebar.selectbox("Select Stock", stocks)

# Corrected Dropdown for indices
indices = {
    "NIFTY 50": "^NSEI",
    "NIFTY BANK": "^NSEBANK",
    "NIFTY IT": "^CNXIT",
    "NIFTY FMCG": "^CNXFMCG",
    "NIFTY AUTO": "^CNXAUTO",
    "SENSEX": "^BSESN"
}
selected_index_name = st.sidebar.selectbox("Select Index", list(indices.keys()))
selected_index_symbol = indices[selected_index_name]

# Function to get price data with error handling
def get_price_data(symbol, period="3mo", interval="1d"):
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period, interval=interval)
        if data.empty:
            st.warning(f"⚠️ No data found for {symbol}. It may be an invalid or delisted symbol.")
            return None
        return data
    except Exception as e:
        st.error(f"❌ Failed to fetch data for {symbol}: {e}")
        return None

# TAB 1 - Technical Dashboard
with tab1:
    st.subheader(f"📈 Technical Chart for {selected_symbol}")
    data = get_price_data(selected_symbol)

    if data is not None:
        st.line_chart(data["Close"])

# TAB 2 - Index Overview
with tab2:
    st.subheader(f"📘 Index Chart: {selected_index_name}")
    index_data = get_price_data(selected_index_symbol)

    if index_data is not None:
        st.line_chart(index_data["Close"])

# TAB 3 - F&O Option Chain (NSE Live)
def get_option_chain(symbol, is_index=True):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9"
    }
    base_url = "https://www.nseindia.com"
    url = f"{base_url}/api/option-chain-{'indices' if is_index else 'equities'}?symbol={symbol}"

    try:
        session = requests.Session()
        session.get(base_url, headers=headers)
        response = session.get(url, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Failed to fetch option chain data. Status code: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"❌ NSE scraping error: {e}")
        return None

with tab3:
    st.subheader("💰 Option Chain Data (NSE Live)")
    option_symbols = list(indices.keys()) + [s.split(".")[0] for s in stocks]
    oc_selection = st.selectbox("Select F&O Symbol (Index or Stock)", option_symbols)

    is_index = oc_selection in indices
    oc_symbol = indices[oc_selection] if is_index else oc_selection

    data = get_option_chain(oc_symbol, is_index=is_index)

    if data:
        ce_data = []
        pe_data = []
        records = data["records"]
        expiry = records.get("expiryDates", [])[0]

        for item in records["data"]:
            strike = item["strikePrice"]
            ce = item.get("CE", {}).get("expiryDate") == expiry and item.get("CE")
            pe = item.get("PE", {}).get("expiryDate") == expiry and item.get("PE")

            if ce:
                ce_data.append({
                    "Strike": strike,
                    "IV": ce.get("impliedVolatility"),
                    "LTP": ce.get("lastPrice"),
                    "OI": ce.get("openInterest")
                })
            if pe:
                pe_data.append({
                    "Strike": strike,
                    "IV": pe.get("impliedVolatility"),
                    "LTP": pe.get("lastPrice"),
                    "OI": pe.get("openInterest")
                })

        st.write("📈 Call Options")
        st.dataframe(pd.DataFrame(ce_data))

        st.write("📉 Put Options")
        st.dataframe(pd.DataFrame(pe_data))
    else:
        st.info("🔄 Could not retrieve option chain data. Try again later.")
