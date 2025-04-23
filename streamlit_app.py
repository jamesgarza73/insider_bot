# app.py
import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime


FMP_KEY = st.secrets["FMP_KEY"]
SAVE_PATH = "data/trades.csv"

st.set_page_config(page_title="Congress Trades AI", layout="wide")
st.title("📊 Congressional Trading Dashboard")

# --- Load Trades
@st.cache_data(ttl=60)
def load_trades():
    try:
        return pd.read_csv(SAVE_PATH, parse_dates=["transactionDate", 
        "disclosureDate", "RunDate",], low_memory=False)
    except (pd.errors.EmptyDataError, ValueError):
        return pd.DataFrame(columns=["disclosureDate", "Ticker", "transactionDate", "firstName", "lastName", "type", "Amount"])


df = load_trades()
df = df.rename(columns={
    "Transaction": "Side", "Ticker": "Ticker", "TransactionDate": "transactionDate",
    "Amount": "Amount", "firstName": "First", "lastName": "Last"
})

# --- Sidebar Filters
st.sidebar.header("📁 Filters")
unique_tickers = sorted(df["symbol"].dropna().unique())
selected_ticker = st.sidebar.selectbox("Select Ticker", ["All"] + unique_tickers)

df['transactionDate'] = df['transactionDate'].dt.strftime('%Y-%m-%d')
df['transactionDate'] = pd.to_datetime(df['transactionDate'])

if not df.empty:
    default_start = df["transactionDate"].min().date()
    default_end = df["transactionDate"].max().date()
else:
    default_start = datetime.today().date()
    default_end = datetime.today().date()


start_date = st.sidebar.date_input("Start Date", default_start)
end_date = st.sidebar.date_input("End Date", default_end)

first_name = st.sidebar.text_input("First Name Filter").strip()
last_name = st.sidebar.text_input("Last Name Filter").strip()

# --- Apply Filters
df_filtered = df.copy()
latest_trade = None
if not df_filtered.empty:
    df_filtered["RunDateTime"] = pd.to_datetime(df_filtered["RunDate"].astype(str) + " " + df_filtered["RunTime"].astype(str), errors="coerce")
    latest_trade = df_filtered.sort_values("RunDateTime", ascending=False).iloc[0]
    
if selected_ticker != "All":
    df_filtered = df_filtered[df_filtered["symbol"] == selected_ticker]
if first_name:
    df_filtered = df_filtered[df_filtered["First"].str.contains(first_name, case=False, na=False)]
if last_name:
    df_filtered = df_filtered[df_filtered["Last"].str.contains(last_name, case=False, na=False)]

# Format dates BEFORE displaying
if not df_filtered.empty:
    for col in ["disclosureDate", "transactionDate","RunDate"]:
        if col in df_filtered.columns:
            df_filtered[col] = pd.to_datetime(df_filtered[col]).dt.date
            df[col] = pd.to_datetime(df[col]).dt.date

st.subheader("📃 Historical Trade Records")
st.dataframe(df_filtered, use_container_width=True)

# --- Stock Chart + Indicators
def get_chart_data(symbol):
    url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol}?apikey={FMP_KEY}&timeseries=60"
    r = requests.get(url)
    r.raise_for_status()
    hist = r.json().get("historical", [])
    return pd.DataFrame(hist)

def add_indicators(df):
    df["RSI"] = df["close"].rolling(window=14).apply(lambda x: 100 - (100 / (1 + (x.pct_change().mean()/x.pct_change().std()))))
    df["MACD"] = df["close"].ewm(span=12).mean() - df["close"].ewm(span=26).mean()
    df["Signal"] = df["MACD"].ewm(span=9).mean()
    return df

if selected_ticker != "All":
    st.subheader(f"📈 Last 60 Days: {selected_ticker}")
    try:
        chart_df = get_chart_data(selected_ticker)
        chart_df["date"] = pd.to_datetime(chart_df["date"])
        chart_df = chart_df.sort_values("date")

        fig = go.Figure()

        # OHLC candlestick trace
        fig.add_trace(go.Candlestick(
            x=chart_df["date"],
            open=chart_df["open"],
            high=chart_df["high"],
            low=chart_df["low"],
            close=chart_df["close"],
            name="OHLC"
        ))

        # Volume trace (secondary y-axis)
        fig.add_trace(go.Bar(
            x=chart_df["date"],
            y=chart_df["volume"],
            name="Volume",
            marker=dict(color='rgba(0, 0, 255, 0.2)'),
            yaxis='y2'
        ))

        # Layout with dual y-axes
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Price",
            yaxis2=dict(
                title="Volume",
                overlaying="y",
                side="right",
                showgrid=False
            ),
            height=600,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error loading chart: {e}")
