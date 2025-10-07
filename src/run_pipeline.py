from .common.config import DATA_RAW, REPORT_DIR, TIMELINE_START, TIMELINE_END, TIMEZONE, YEARS, MAX_WEIGHT
from .common.universe import TICKERS, CLASSIFICATION
from .ingestion.yfinance_client import collect
from .data_io.yaml_store import save_frames, load_frames
from .analytics.optimizer import build_yearly_portfolios
from .reporting.yaml_reporter import write_reports


def main():
    frames = collect(TICKERS, TIMELINE_START, TIMELINE_END, TIMEZONE)
    save_frames(frames, DATA_RAW)
    loaded = load_frames(TICKERS, DATA_RAW)
    portfolios = build_yearly_portfolios(loaded, CLASSIFICATION, YEARS, MAX_WEIGHT)
    write_reports(portfolios, REPORT_DIR)


if __name__ == "__main__":
    main()
