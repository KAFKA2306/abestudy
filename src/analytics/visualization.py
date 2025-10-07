from pathlib import Path
import math
import os
import warnings

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
import pandas as pd
import yaml
import yfinance as yf

from ..common.config import DATA_RAW, REPORT_DIR, TICKER_NAMES_FILE
from ..data_io.yaml_store import load_frames


def _load_ticker_names():
    if not TICKER_NAMES_FILE.exists():
        return {}
    return yaml.safe_load(TICKER_NAMES_FILE.read_text(encoding="utf-8"))


def _load_portfolios(ticker_names):
    portfolios = {}
    for path in sorted(REPORT_DIR.glob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if "year" not in payload:
            continue
        year = int(payload["year"])
        allocation = payload.get("portfolio", {}).get("allocations", {})
        holdings = allocation.get("top_holdings", [])
        if not holdings:
            continue
        ordered = sorted(holdings, key=lambda item: float(item.get("weight", 0.0)), reverse=True)[:10]
        parsed_holdings = [
            {
                "ticker": item["ticker"],
                "weight": float(item.get("weight", 0.0)),
                "name": ticker_names.get(item["ticker"], item.get("name", item["ticker"])),
            }
            for item in ordered
        ]
        if not parsed_holdings:
            continue
        evaluation_window = payload.get("conditions", {}).get("evaluation_window", {})
        start = evaluation_window.get("start")
        end = evaluation_window.get("end")
        if start is None or end is None:
            continue
        start_ts = pd.Timestamp(start).tz_localize(None)
        end_ts = pd.Timestamp(end).tz_localize(None)
        portfolios[year] = {"holdings": parsed_holdings, "start": start_ts, "end": end_ts}
    return portfolios


def _load_closes(tickers, start=None, end=None, allow_downloads=None):
    if not tickers:
        return pd.DataFrame()

    tickers = sorted(set(tickers))
    available_locally = [ticker for ticker in tickers if (DATA_RAW / f"{ticker}.yaml").exists()]
    series_map = {}

    if available_locally:
        frames = load_frames(available_locally, DATA_RAW)
        for ticker, frame in frames.items():
            if "close" in frame:
                close_series = frame["close"].copy()
                close_series.index = pd.to_datetime(close_series.index)
                if getattr(close_series.index, "tz", None) is not None:
                    close_series.index = close_series.index.tz_localize(None)
                series_map[ticker] = close_series.sort_index()

    missing = [ticker for ticker in tickers if ticker not in series_map]
    if allow_downloads is None:
        allow_downloads = os.getenv("ABESTUDY_ALLOW_REMOTE_DATA", "").lower() in {"1", "true", "yes"}

    if missing and allow_downloads and start is not None and end is not None:
        download_start = (start - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
        download_end = (end + pd.Timedelta(days=7)).strftime("%Y-%m-%d")
        for ticker in missing:
            try:
                history = yf.download(
                    ticker,
                    start=download_start,
                    end=download_end,
                    progress=False,
                    auto_adjust=True,
                )
            except Exception:
                continue
            if history.empty or "Close" not in history:
                continue
            close_series = history["Close"].copy()
            close_series.index = pd.to_datetime(close_series.index)
            if getattr(close_series.index, "tz", None) is not None:
                close_series.index = close_series.index.tz_localize(None)
            series_map[ticker] = close_series.sort_index()
    elif missing:
        warnings.warn(
            "Skipping download for tickers without local data: " + ", ".join(sorted(missing)),
            RuntimeWarning,
            stacklevel=2,
        )

    closes = pd.DataFrame(series_map)
    closes = closes.sort_index()
    if getattr(closes.index, "tz", None) is not None:
        closes.index = closes.index.tz_localize(None)
    return closes


def create_yearly_portfolio_panels(output_path: Path) -> Path:
    ticker_names = _load_ticker_names()
    portfolios = _load_portfolios(ticker_names)
    if not portfolios:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(
            0.5,
            0.5,
            "No portfolio data available",
            ha="center",
            va="center",
            fontsize=12,
            color="dimgray",
        )
        ax.axis("off")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.tight_layout()
        fig.savefig(output_path, format=output_path.suffix.lstrip("."))
        plt.close(fig)
        return output_path

    years_with_data = sorted(portfolios)
    full_year_range = list(range(min(years_with_data), max(years_with_data) + 1))
    tickers = sorted({holding["ticker"] for info in portfolios.values() for holding in info["holdings"]})
    global_start = min(info["start"] for info in portfolios.values())
    global_end = max(info["end"] for info in portfolios.values())
    closes = _load_closes(tickers, global_start, global_end) if tickers else pd.DataFrame()

    cols = 1
    rows = len(full_year_range)
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 12, rows * 5))
    axes = [axes] if isinstance(axes, Axes) else list(axes.ravel())

    cmap = plt.get_cmap("viridis")
    colors = {ticker: cmap(i / len(tickers)) for i, ticker in enumerate(tickers)}

    for ax, year in zip(axes, full_year_range):
        ax.set_facecolor("#f9f9f9")
        if year not in portfolios:
            ax.text(
                0.5,
                0.5,
                f"No data for {year}",
                ha="center",
                va="center",
                fontsize=12,
                color="dimgray",
            )
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title(str(year), fontsize=14, fontweight="bold")
            continue

        info = portfolios[year]
        weights = pd.Series({holding["ticker"]: holding["weight"] for holding in info["holdings"]}, dtype=float)
        available_tickers = [ticker for ticker in weights.index if not closes.empty and ticker in closes.columns]

        if not available_tickers:
            ax.text(
                0.5,
                0.5,
                "No local price data",
                ha="center",
                va="center",
                fontsize=12,
                color="dimgray",
            )
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title(str(year), fontsize=14, fontweight="bold")
            continue

        weights = weights.loc[available_tickers]
        weights = weights / weights.sum()
        subset = closes.loc[:, available_tickers]

        valid_columns = []
        start_dates = []
        for ticker, series in subset.items():
            cleaned = series.dropna()
            if cleaned.empty:
                continue
            valid_columns.append(ticker)
            start_dates.append(cleaned.index.min())

        if not valid_columns:
            ax.text(
                0.5,
                0.5,
                "Insufficient price history",
                ha="center",
                va="center",
                fontsize=12,
                color="dimgray",
            )
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title(str(year), fontsize=14, fontweight="bold")
            continue

        subset = subset.loc[:, valid_columns]
        start = max(start_dates + [info["start"]])
        subset = subset.loc[subset.index >= start]
        subset = subset.ffill()

        if subset.empty:
            ax.text(
                0.5,
                0.5,
                "No prices after start date",
                ha="center",
                va="center",
                fontsize=12,
                color="dimgray",
            )
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title(str(year), fontsize=14, fontweight="bold")
            continue

        base = subset.iloc[0]
        normalized = subset.divide(base)
        scaled = normalized * 100
        portfolio_curve = scaled.mul(weights, axis=1).sum(axis=1)

        for ticker in scaled.columns:
            name = ticker_names.get(ticker, ticker)
            ax.plot(
                scaled.index,
                scaled[ticker],
                linewidth=1.5,
                alpha=0.8,
                color=colors.get(ticker, "#555555"),
                label=f"{name} ({weights[ticker]:.1%})",
            )

        ax.plot(
            portfolio_curve.index,
            portfolio_curve,
            linewidth=2.5,
            color="black",
            label="Portfolio",
        )

        ax.set_title(str(year), fontsize=14, fontweight="bold")
        ax.set_ylabel("Indexed performance (base = 100)", fontsize=10)
        ax.set_xlabel("Date", fontsize=10)
        ax.grid(alpha=0.5, linestyle="--", linewidth=0.8)
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax.tick_params(axis="x", rotation=30, labelsize=9)
        ax.tick_params(axis="y", labelsize=9)
        ax.legend(fontsize=9, ncol=2, frameon=True, loc="upper left", facecolor="white", framealpha=0.8)
        ax.set_xlim(global_start, global_end)


    for ax in axes[len(full_year_range):]:
        fig.delaxes(ax)

    fig.suptitle("Portfolio Performance by Year", fontsize=18, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, format=output_path.suffix.lstrip("."), dpi=150)
    plt.close(fig)
    return output_path
