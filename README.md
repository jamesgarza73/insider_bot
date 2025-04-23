# insider_bot
Insider information (congress and institutional) trading bot. The information is public.
congress_app/
├── update_trades.py        ← 🛰️ Background fetcher + AI analyzer
├── app.py                  ← 🎛️ Streamlit UI for exploration
├── data/
│   └── trades.csv          ← 📦 Persistent trade history
├── .streamlit/
│   └── secrets.toml        ← 🔐 API keys go here
