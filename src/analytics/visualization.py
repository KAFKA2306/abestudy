from pathlib import Path
import math

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
import pandas as pd
import yaml

from ..common.config import DATA_RAW, REPORT_DIR
from ..data_io.yaml_store import load_frames


def _load_portfolios():
    portfolios = {}
    for path in sorted(REPORT_DIR.glob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if "year" not in payload:
            continue
        year = int(payload["year"])
        holdings = payload["portfolio"]["allocations"]["top_holdings"][:10]
        weights = {item["ticker"]: float(item["weight"]) for item in holdings}
        weights = {ticker: weight for ticker, weight in weights.items() if (DATA_RAW / f"{ticker}.yaml").exists()}
        if not weights:
            continue
        start = pd.Timestamp(payload["conditions"]["evaluation_window"]["start"]).tz_localize(None)
        portfolios[year] = {"weights": weights, "start": start}
    return portfolios


def _load_closes(tickers):
    frames = load_frames(tickers, DATA_RAW)
    closes = pd.DataFrame({ticker: frame["close"] for ticker, frame in frames.items()})
    closes = closes.sort_index()
    if getattr(closes.index, "tz", None) is not None:
        closes.index = closes.index.tz_localize(None)
    return closes


def create_yearly_portfolio_panels(output_path: Path) -> Path:
    portfolios = _load_portfolios()
    years = sorted(portfolios)
    tickers = sorted({ticker for info in portfolios.values() for ticker in info["weights"]})
    closes = _load_closes(tickers)
    cols = 2
    rows = math.ceil(len(years) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 6, rows * 4))
    axes = [axes] if isinstance(axes, Axes) else list(axes.ravel())
    for ax, year in zip(axes, years):
        info = portfolios[year]
        weights = pd.Series(info["weights"], dtype=float)
        weights = weights / weights.sum()
        subset = closes.loc[:, weights.index]
        start_dates = [series.dropna().index.min() for _, series in subset.items()]
        start = max(start_dates + [info["start"]])
        subset = subset.loc[subset.index >= start]
        subset = subset.ffill()
        base = subset.iloc[0]
        normalized = subset.divide(base)
        scaled = normalized * 100
        portfolio_curve = scaled.mul(weights, axis=1).sum(axis=1)
        for ticker in scaled.columns:
            axes_label = ticker
            ax.plot(scaled.index, scaled[ticker], linewidth=0.8, alpha=0.7, label=axes_label)
        ax.plot(portfolio_curve.index, portfolio_curve, linewidth=1.6, color="black", label="portfolio")
        ax.set_title(str(year))
        ax.set_ylabel("Index")
        ax.set_xlabel("Date")
        ax.legend(fontsize=7, ncol=2)
    for ax in axes[len(years):]:
        fig.delaxes(ax)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, format=output_path.suffix.lstrip("."))
    plt.close(fig)
    return output_path
