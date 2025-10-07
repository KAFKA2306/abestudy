from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_RAW = BASE_DIR / "data" / "raw"
REPORT_DIR = BASE_DIR / "reports" / "portfolio"
REFERENCE_DIR = BASE_DIR / "data" / "reference"
TICKER_NAMES_FILE = REFERENCE_DIR / "ticker_names.yaml"
TIMELINE_START = "2009-01-01"
TIMELINE_END = "2023-12-31"
ABENOMICS_START = "2012-12-26"
ABENOMICS_END = "2020-09-16"
YEARS = range(2013, 2021)
TIMEZONE = "Asia/Tokyo"
MAX_WEIGHT = 0.2
TRADING_DAYS = 252
LOOKBACK_DAYS = 252
MIN_TRAINING_OBSERVATIONS = 120
