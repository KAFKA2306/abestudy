from pathlib import Path
from typing import Iterable, Mapping

import matplotlib.pyplot as plt
import pandas as pd

from ..common.config import (
    ABENOMICS_END,
    ABENOMICS_START,
    DATA_RAW,
)
from ..common.universe import TICKER_NAMES
from ..data_io.yaml_store import load_frames


def _load_closing_prices(tickers: Iterable[str]) -> pd.DataFrame:
    frames = load_frames(tickers, DATA_RAW)
    closes = pd.DataFrame({ticker: frame["close"] for ticker, frame in frames.items()})
    closes = closes.sort_index()
    if hasattr(closes.index, "tz") and closes.index.tz is not None:
        closes.index = closes.index.tz_localize(None)
    return closes


def _normalize_to_policy_start(closes: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    normalized = {}
    for ticker, series in closes.items():
        clean_series = series.dropna()
        if clean_series.empty:
            continue
        anchor = clean_series.loc[clean_series.index >= start]
        if anchor.empty:
            continue
        base_price = anchor.iloc[0]
        normalized[ticker] = clean_series / base_price * 100
    if not normalized:
        return pd.DataFrame()
    frame = pd.DataFrame(normalized)
    frame = frame.sort_index()
    return frame


def create_abenomics_performance_chart(
    tickers: Iterable[str],
    output_path: Path,
    ticker_names: Mapping[str, str] = TICKER_NAMES,
) -> Path:
    start = pd.Timestamp(ABENOMICS_START)
    end = pd.Timestamp(ABENOMICS_END)

    closes = _load_closing_prices(tickers)
    normalized = _normalize_to_policy_start(closes, start)

    period_start = start - pd.DateOffset(years=3)
    period_end = end + pd.DateOffset(years=1)
    window = normalized.loc[(normalized.index >= period_start) & (normalized.index <= period_end)]

    labels = {ticker: ticker_names.get(ticker, ticker) for ticker in window.columns}

    palette = plt.get_cmap("tab10")
    colors = {ticker: palette(i % 10) for i, ticker in enumerate(window.columns)}
    annual_leaders = []
    for year, frame in normalized.groupby(normalized.index.year):
        if year < start.year or year > end.year:
            continue
        frame = frame.dropna(how="all")
        if frame.empty:
            continue
        first = frame.iloc[0]
        last = frame.iloc[-1]
        performance = (last / first) - 1
        performance = performance.dropna()
        if performance.empty:
            continue
        leader = performance.idxmax()
        annual_leaders.append((year, leader, performance[leader] * 100))

    fig, axes = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={"height_ratios": [2, 1]})
    ax = axes[0]
    for ticker in window.columns:
        ax.plot(window.index, window[ticker], label=labels[ticker], color=colors[ticker])

    ax.axvspan(start, end, color="#d946ef", alpha=0.12, label="Abenomics policy window")
    ax.set_title("Abenomics Era Performance of Key Japanese Stocks")
    ax.set_ylabel("Normalized closing price (2012-12-26 = 100)")
    ax.set_xlabel("Date")
    ax.legend(loc="upper left", frameon=False)
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)

    bar_ax = axes[1]
    years = [str(year) for year, _, _ in annual_leaders]
    returns = [value for _, _, value in annual_leaders]
    leaders = [leader for _, leader, _ in annual_leaders]
    bar_colors = [colors.get(ticker, "#999999") for ticker in leaders]
    bars = bar_ax.bar(years, returns, color=bar_colors)
    for bar, ticker, ret in zip(bars, leaders, returns):
        name = labels.get(ticker, ticker)
        offset = 1.5 if ret >= 0 else -1.5
        va = "bottom" if ret >= 0 else "top"
        bar_ax.text(bar.get_x() + bar.get_width() / 2, ret + offset, f"{name}\n{ret:.1f}%", ha="center", va=va, fontsize=9)
    bar_ax.set_ylabel("Annual return (%)")
    bar_ax.set_title("Top performer by year")
    bar_ax.axhline(0, color="#666666", linewidth=0.8)
    bar_ax.set_ylim(min(returns + [0]) - 5, max(returns + [0]) + 5)
    bar_ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.5)

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, format=output_path.suffix.lstrip("."))
    plt.close(fig)
    return output_path
