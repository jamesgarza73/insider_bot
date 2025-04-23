# 🏛️ Congress Trades AI Tracker

A real-time Streamlit app that tracks and analyses U.S. Congress stock trades 🧑‍⚖️📈. Pulls data from the Financial Modelling Prep API, processes trading activity, and uses Openai to generate actionable long/short signals based on congressional flows.

## 📦 Project Structure


congress_app/
├── update_trades.py        ← 🛰️ Background fetcher + AI analyzer

├── app.py                  ← 🎛️ Streamlit UI for exploration

├── data/

│   └── trades.csv          ← 📦 Persistent trade history

├── .streamlit/

│   └── secrets.toml        ← 🔐 API keys go here
