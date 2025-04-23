import os, time, json, re, warnings
import pandas as pd
import requests
from datetime import datetime
from openai import AsyncClient
import asyncio
from dotenv import load_dotenv
import subprocess

warnings.filterwarnings("ignore", category=RuntimeWarning)  # Silence unretrieved future warnings

# Load secrets from .env
load_dotenv()
FMP_KEY = os.getenv("FMP_KEY")
OPENAI_KEY = os.getenv("OPENAI_KEY")
MODEL_NAME = "gpt-4o-mini"
SAVE_PATH = "/home/jamesgarza/congress_app/data/trades.csv"

def git_push():
    try:
        subprocess.run(["git", "add", "data/trades.csv"], check=True)
        subprocess.run(["git", "commit", "-m", f"Update trades {datetime.now()}"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("✅ Pushed trades.csv to GitHub")
    except subprocess.CalledProcessError as e:
        print("🔥 Git error:", e)

def parse_amount(s: str) -> float:
    if not s or "Undisclosed" in s: return 0.0
    hi_lo = s.replace("$", "").split("–")
    lo, hi = [float(p.replace(',', '')) for p in re.findall(r'[\d,]+', hi_lo[0])]
    return (lo + hi)/2

def extract_json(raw_text):
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        return json.loads(match.group())
    else:
        raise ValueError("⚠️ No valid JSON found in OpenAI response.")

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

async def get_ai_signals(df_top: pd.DataFrame):
    summary = df_top.head(20).to_csv(index=False)
    prompt = (
        "Here are today’s top 20 tickers by net congressional flow:\n\n"
        + summary + "\n\n"
        "Think like a hedge‑fund manager. Select up to 6 tickers to LONG and up to 6 to SHORT, "
        "considering net flow, recent performance, market conditions and news.\n\n"
        "⚠️ IMPORTANT: Reply *only* with one valid JSON object matching this schema:\n"
        "{\n"
        '  "long": [\n'
        '    { "ticker": "SYM1", "rationale": "Why go long on SYM1" },\n'
        '    ... up to 6 entries ...\n'
        "  ],\n"
        '  "short": [\n'
        '    { "ticker": "SYM2", "rationale": "Why short SYM2" },\n'
        '    ... up to 6 entries ...\n'
        "  ]\n"
        "}\n\n"
        "Use double quotes everywhere; do not wrap in markdown fences or add any extra text. "
        "If you can’t pick 6, return as many as you can; if none are viable, return `{}`."
    )

    async with AsyncClient(api_key=OPENAI_KEY) as client:
        resp = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400
        )
        return resp.choices[0].message.content

def get_ai_signals_sync(df_top):
    async def wrapper():
        return await get_ai_signals(df_top)
    return asyncio.run(wrapper())

def main():
    os.makedirs("data", exist_ok=True)
    df_new = fetch_congress_trades()
    df_new["amount"] = df_new["amount"].apply(parse_amount)
    df_new["net_usd"] = df_new.apply(lambda r: r["amount"] * (1 if r["type"] == "Purchase" else -1), axis=1)

    if os.path.exists(SAVE_PATH):
        df_old = pd.read_csv(SAVE_PATH)
        combined = pd.concat([df_old, df_new], ignore_index=True).drop_duplicates(subset=["disclosureDate", "symbol", "transactionDate"])
    else:
        combined = df_new

    net_by_ticker = combined.groupby("symbol", as_index=False)["net_usd"].sum().sort_values("net_usd", ascending=False)

    try:
        raw = get_ai_signals_sync(net_by_ticker)
        data = extract_json(raw)
    except Exception as e:
        print("🔥 OpenAI Error:", e)
        return

    rows = []
    for item in data.get('long', []):
        rows.append({'symbol': item['ticker'], 'position': 'long', 'rationale': item['rationale']})
    for item in data.get('short', []):
        rows.append({'symbol': item['ticker'], 'position': 'short', 'rationale': item['rationale']})

    df_signals = pd.DataFrame(rows)

    cols_to_add = ['symbol','disclosureDate', 'transactionDate', 'firstName', 'lastName',
                   'office', 'district', 'owner', 'assetDescription', 'assetType', 'type',
                   'amount', 'comment', 'link', 'chamber', 'capitalGainsOver200USD',
                   'net_usd']

    df_signals = df_signals.merge(df_new[cols_to_add], how='left', on='symbol')

    df_signals = df_signals.groupby('symbol').agg({
        'position': 'first',
        'rationale': 'first',
        'disclosureDate': 'first',
        'transactionDate': 'first',
        'firstName': 'first',
        'lastName': 'first',
        'office': 'first',
        'owner': 'first',
        'assetDescription': 'first',
        'assetType': 'first',
        'type': 'first',
        'amount': 'sum',
        'comment': 'first',
        'link': 'first',
        'chamber': 'first',
        'capitalGainsOver200USD': 'sum',
        'net_usd': 'sum'
    }).reset_index()

    df_signals.drop(columns=['comment', 'capitalGainsOver200USD', 'net_usd'], inplace=True)

    df_signals.to_csv(SAVE_PATH, index=False)
    print(f"[{datetime.now()}] ✅ Saved {len(df_signals)} rows")
    git_push()

if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            print("🔥 Error:", e)
        time.sleep(60)
