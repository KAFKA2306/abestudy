from pathlib import Path

from .analytics.visualization import create_abenomics_performance_chart
from .common.config import BASE_DIR


DEFAULT_TICKERS = ["6758.T", "7203.T", "8035.T", "9984.T", "8306.T"]


def main() -> Path:
    output = BASE_DIR / "reports" / "figures" / "abenomics_stock_performance.svg"
    return create_abenomics_performance_chart(DEFAULT_TICKERS, output)


if __name__ == "__main__":
    path = main()
    print(path)
