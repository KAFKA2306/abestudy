from .common.config import (
    DATA_RAW,
    REPORT_DIR,
    TIMELINE_START,
    TIMELINE_END,
    TIMEZONE,
    YEARS,
    MAX_WEIGHT,
    LOOKBACK_DAYS,
    MIN_TRAINING_OBSERVATIONS,
)
from .common.universe import ALL_TICKERS, load_names, universe_for_year
from .ingestion.yfinance_client import collect
from .data_io.yaml_store import save_frames, load_frames
from .analytics.optimizer import build_yearly_portfolios
from .reporting.yaml_reporter import write_reports
def main():
    names = load_names()
    frames = collect(ALL_TICKERS, TIMELINE_START, TIMELINE_END, TIMEZONE)
    save_frames(frames, DATA_RAW)
    loaded = load_frames(ALL_TICKERS, DATA_RAW)
    portfolios = build_yearly_portfolios(
        loaded,
        YEARS,
        MAX_WEIGHT,
        LOOKBACK_DAYS,
        MIN_TRAINING_OBSERVATIONS,
        universe_for_year,
        names,
    )
    write_reports(portfolios, REPORT_DIR)
if __name__ == "__main__":
    main()
