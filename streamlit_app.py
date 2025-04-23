# app.py
import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime

FMP_KEY = st.secrets["fmp_key"]
SAVE_PATH = "data/trades.csv"

st.set_page_config(page_title="Congress Trades AI", layout="wide")
st.title("📊 Congressional Trading Dashboard")

# --- Load Trades
@st.cache_data(ttl=60)
def load_trades():
    return pd.read_csv(SAVE_PATH, parse_dates=["TransactionDate", "disclosureDate"], low_memory=False)

df = load_trades()
df = df.rename(columns={
    "Transaction": "Side", "Ticker": "Ticker", "TransactionDate": "TransactionDate",
    "Amount": "Amount", "firstName": "First", "lastName": "Last"
})

# --- Sidebar Filters
st.sidebar.header("📁 Filters")
unique_tickers = sorted(df["Ticker"].dropna().unique())
selected_ticker = st.sidebar.selectbox("Select Ticker", ["All"] + unique_tickers)

start_date = st.sidebar.date_input("Start Date", df["TransactionDate"].min().date())
end_date = st.sidebar.date_input("End Date", df["TransactionDate"].max().date())

first_name = st.sidebar.text_input("First Name Filter").strip()
last_name = st.sidebar.text_input("Last Name Filter").strip()

# --- Apply Filters
df_filtered = df.copy()
df_filtered = df_filtered[df_filtered["TransactionDate"].between(str(start_date), str(end_date))]
if selected_ticker != "All":
    df_filtered = df_filtered[df_filtered["Ticker"] == selected_ticker]
if first_name:
    df_filtered = df_filtered[df_filtered["First"].str.contains(first_name, case=False, na=False)]
if last_name:
    df_filtered = df_filtered[df_filtered["Last"].str.contains(last_name, case=False, na=False)]

st.subheader("📃 Historical Trade Records")
st.dataframe(df_filtered, use_container_width=True)

# --- Stock Chart + Indicators
def get_chart_data(symbol):
    url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol}?apikey={FMP_KEY}&serietype=line"
    data = requests.get(url).json()
    return pd.DataFrame(data['historical'])

def add_indicators(df):
    df["RSI"] = df["close"].rolling(window=14).apply(lambda x: 100 - (100 / (1 + (x.pct_change().mean()/x.pct_change().std()))))
    df["MACD"] = df["close"].ewm(span=12).mean() - df["close"].ewm(span=26).mean()
    df["Signal"] = df["MACD"].ewm(span=9).mean()
    return df

if selected_ticker != "All":
    st.subheader(f"📈 Chart for {selected_ticker}")
    try:
        chart_df = get_chart_data(selected_ticker)
        chart_df = add_indicators(chart_df)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=chart_df["date"], y=chart_df["close"], name="Close Price"))
        fig.add_trace(go.Scatter(x=chart_df["date"], y=chart_df["RSI"], name="RSI"))
        fig.add_trace(go.Scatter(x=chart_df["date"], y=chart_df["MACD"], name="MACD"))
        fig.add_trace(go.Scatter(x=chart_df["date"], y=chart_df["Signal"], name="MACD Signal"))
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading chart: {e}")
