from pathlib import Path

from .analytics.visualization import create_yearly_portfolio_panels
from .common.config import BASE_DIR


def main() -> Path:
    output = BASE_DIR / "reports" / "figures" / "yearly_portfolio_longrun.svg"
    return create_yearly_portfolio_panels(output)


if __name__ == "__main__":
    path = main()
    print(path)
