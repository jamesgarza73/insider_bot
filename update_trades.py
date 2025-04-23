# update_trades.py
import os, time, json, re, ast
import pandas as pd
import requests
from datetime import datetime
from openai import AsyncClient
import asyncio

FMP_KEY = os.getenv("FMP_KEY")
OPENAI_KEY = os.getenv("OPENAI_KEY")
MODEL_NAME = "gpt-4o-mini"

SAVE_PATH = "data/trades.csv"

def parse_amount(s: str) -> float:
    if not s or "Undisclosed" in s: return 0.0
    hi_lo = s.replace("$", "").split("–")
    lo, hi = [float(p.replace(',', '')) for p in re.findall(r'[\d,]+', hi_lo[0])]
    return (lo + hi)/2

def fetch_congress_trades():
    endpoints = {
        "senate": f"https://financialmodelingprep.com/stable/senate-latest?page=0&limit=100&apikey={FMP_KEY}",
        "house":  f"https://financialmodelingprep.com/stable/house-latest?page=0&limit=100&apikey={FMP_KEY}"
    }
    dfs = []
    for chamber, url in endpoints.items():
        r = requests.get(url); r.raise_for_status()
        df = pd.DataFrame(r.json())
        df["chamber"] = chamber
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)

async def get_ai_signals(net_df: pd.DataFrame):
    summary = net_df.head(20).to_csv(index=False)
    prompt = f"""
Here are today’s top 20 tickers by net congressional flow:\n\n{summary}

Think like a hedge-fund manager. Select up to 6 to LONG and 6 to SHORT. Respond only with valid JSON:
{{
  "long": [{{ "ticker": "SYM1", "rationale": "Reason" }}],
  "short": [{{ "ticker": "SYM2", "rationale": "Reason" }}]
}}
"""
    client = AsyncClient(api_key=OPENAI_KEY)
    resp = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400
    )
    return ast.literal_eval(resp.choices[0].message.content)

def main():
    os.makedirs("data", exist_ok=True)
    df_new = fetch_congress_trades()
    df_new["amount"] = df_new["Amount"].apply(parse_amount)
    df_new["net_usd"] = df_new.apply(lambda r: r["amount"] * (1 if r["type"] == "Purchase" else -1), axis=1)

    if os.path.exists(SAVE_PATH):
        df_old = pd.read_csv(SAVE_PATH)
        combined = pd.concat([df_old, df_new], ignore_index=True).drop_duplicates(subset=["disclosureDate", "Ticker", "TransactionDate"])
    else:
        combined = df_new

    combined.to_csv(SAVE_PATH, index=False)
    print(f"[{datetime.now()}] ✅ Saved {len(combined)} rows")

    net_by_ticker = combined.groupby("Ticker", as_index=False)["net_usd"].sum().sort_values("net_usd", ascending=False)
    ai_result = asyncio.run(get_ai_signals(net_by_ticker))
    print("💡 AI Signals:", ai_result)

if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            print("🔥 Error:", e)
        time.sleep(60)  # rerun every 60 seconds
