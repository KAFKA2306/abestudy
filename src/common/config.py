from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_RAW = BASE_DIR / "data" / "raw"
REPORT_DIR = BASE_DIR / "reports" / "portfolio"
REFERENCE_DIR = BASE_DIR / "data" / "reference"
TICKER_NAMES_FILE = REFERENCE_DIR / "ticker_names.yaml"
UNIVERSE_SNAPSHOTS_FILE = REFERENCE_DIR / "nikkei225_memberships.yaml"
TIMELINE_START = "2000-01-01"
TIMELINE_END = "2025-09-30"
ABENOMICS_START = "2012-12-26"
ABENOMICS_END = "2020-09-16"
YEARS = range(2013, 2021)
TIMEZONE = "Asia/Tokyo"
MAX_WEIGHT = 0.2
TRADING_DAYS = 365
LOOKBACK_DAYS = 365
MIN_TRAINING_OBSERVATIONS = 120
