
import yfinance as yf
import yaml
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path('/home/kafka/projects/abestudy')
TICKER_NAMES_FILE = PROJECT_ROOT / 'data' / 'reference' / 'ticker_names.yaml'
OUTPUT_FILE = PROJECT_ROOT / 'new_universe.yaml'
TIMELINE_START = "2009-01-01"
TIMELINE_END = "2023-12-31"

with open(TICKER_NAMES_FILE, "r") as f:
    ticker_names = yaml.safe_load(f)
TICKERS = list(ticker_names.keys())

long_history_tickers = {}

print("Checking ticker histories...")
for ticker in TICKERS:
    try:
        data = yf.download(ticker, start=TIMELINE_START, end=TIMELINE_END, progress=False, auto_adjust=True)
        if not data.empty:
            first_date = data.index[0]
            if first_date.year == 2009 and first_date.month == 1:
                long_history_tickers[ticker] = ticker_names.get(ticker, 'N/A')
                print(f"[ OK ] {ticker}: Data starts {first_date.date()}")
            else:
                print(f"[SKIP] {ticker}: Data starts {first_date.date()} (too late)")
        else:
            print(f"[SKIP] {ticker}: No data in period")
    except Exception as e:
        print(f"[FAIL] {ticker}: {e}")

print("\n--- Tickers with 13+ years of data ---")
output_tickers = {k: v for k, v in long_history_tickers.items()}
for ticker, name in output_tickers.items():
    print(f'- {ticker}: {name}')

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    for ticker, name in output_tickers.items():
        f.write(f'"{ticker}": {name}\n')

print(f"\nNew universe saved to {OUTPUT_FILE}")
