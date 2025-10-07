import yaml
from src.common.config import TICKER_NAMES_FILE

with open(TICKER_NAMES_FILE, "r") as f:
    TICKER_NAMES = yaml.safe_load(f)

TICKERS = list(TICKER_NAMES.keys())
