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
import numpy as np

from ..common.config import DATA_RAW, REPORT_DIR, TICKER_NAMES_FILE, ABENOMICS_START, ABENOMICS_END, TIMELINE_START
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

def _plot_no_data_message(ax, year, message, global_start, global_end):
    ax.text(
        0.5,
        0.5,
        message,
        ha="center",
        va="center",
        fontsize=12,
        color="dimgray",
    )
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(str(year), fontsize=14, fontweight="bold")
    ax.set_xlim(global_start, global_end)
    ax.set_ylim(0.1, 10) # Changed ylim
    ax.set_yscale('log')

def create_yearly_portfolio_panels(output_path: Path) -> Path:
    ticker_names = _load_ticker_names()
    portfolios = _load_portfolios(ticker_names)
    if not portfolios:
        fig, ax = plt.subplots(figsize=(6, 4))
        _plot_no_data_message(ax, "", "No portfolio data available", None, None) # No year for overall message
        ax.axis("off")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.tight_layout()
        fig.savefig(output_path, format=output_path.suffix.lstrip("."))
        plt.close(fig)
        return output_path

    years_with_data = sorted(portfolios)
    full_year_range = list(range(min(years_with_data), max(years_with_data) + 1))
    tickers = sorted({holding["ticker"] for info in portfolios.values() for holding in info["holdings"]})
    global_start = pd.Timestamp(TIMELINE_START).tz_localize(None) # Changed global_start
    global_end = pd.Timestamp.now().normalize() # Extend to today
    closes = _load_closes(tickers, global_start, global_end) if tickers else pd.DataFrame()

    cols = 1
    rows = len(full_year_range)
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 24, rows * 5)) # Doubled width
    axes = [axes] if isinstance(axes, Axes) else list(axes.ravel())

    cmap = plt.get_cmap("tab20") # Changed colormap to tab20
    colors = {ticker: cmap(i % cmap.N) for i, ticker in enumerate(tickers)} # Use modulo for tab20

    # Convert Abenomics dates to Timestamp objects
    abenomics_start_ts = pd.Timestamp(ABENOMICS_START).tz_localize(None)
    abenomics_end_ts = pd.Timestamp(ABENOMICS_END).tz_localize(None)

    for i, (ax, year) in enumerate(zip(axes, full_year_range)):
        ax.set_facecolor("#f9f9f9")
        ax.set_xlim(global_start, global_end)
        ax.set_ylim(0.1, 10) # Changed ylim
        ax.set_yscale('log')

        if year not in portfolios:
            _plot_no_data_message(ax, year, f"No data for {year}", global_start, global_end)
            # Hide x-axis labels for non-last subplots
            if i < len(full_year_range) - 1:
                ax.set_xlabel('')
                ax.tick_params(labelbottom=False)
            continue

        info = portfolios[year]
        weights = pd.Series({holding["ticker"]: holding["weight"] for holding in info["holdings"]}, dtype=float)
        available_tickers = [ticker for ticker in weights.index if not closes.empty and ticker in closes.columns]

        if not available_tickers:
            _plot_no_data_message(ax, year, "No local price data", global_start, global_end)
            # Hide x-axis labels for non-last subplots
            if i < len(full_year_range) - 1:
                ax.set_xlabel('')
                ax.tick_params(labelbottom=False)
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
            _plot_no_data_message(ax, year, "Insufficient price history", global_start, global_end)
            # Hide x-axis labels for non-last subplots
            if i < len(full_year_range) - 1:
                ax.set_xlabel('')
                ax.tick_params(labelbottom=False)
            continue

        subset = subset.loc[:, valid_columns]
        start = max(start_dates + [info["start"]])
        subset = subset.loc[subset.index >= start]
        subset = subset.ffill()

        if subset.empty:
            _plot_no_data_message(ax, year, "No prices after start date", global_start, global_end)
            # Hide x-axis labels for non-last subplots
            if i < len(full_year_range) - 1:
                ax.set_xlabel('')
                ax.tick_params(labelbottom=False)
            continue

        base = subset.iloc[0]
        normalized = subset.divide(base)
        scaled = normalized * 1 # Changed base from 100 to 1
        portfolio_curve = scaled.mul(weights, axis=1).sum(axis=1)

        # Plot Abenomics period
        ax.axvspan(abenomics_start_ts, abenomics_end_ts, color="gray", alpha=0.2, label="Abenomics Period")

        lines = []
        labels = []
        for ticker in scaled.columns:
            name = ticker_names.get(ticker, ticker)
            line, = ax.plot(
                scaled.index,
                scaled[ticker],
                linewidth=1.5,
                alpha=0.8,
                color=colors.get(ticker, "#555555"),
                label=f"{name} ({weights[ticker]:.1%})",
            )
            lines.append(line)
            labels.append(f"{name} ({weights[ticker]:.1%})")

        portfolio_line, = ax.plot(
            portfolio_curve.index,
            portfolio_curve,
            linewidth=2.5,
            color="black",
            label="Portfolio",
        )
        lines.append(portfolio_line)
        labels.append("Portfolio")

        # Sort legend entries by final indexed performance
        final_values = []
        for line in lines:
            if line.get_label() == "Portfolio":
                final_values.append(portfolio_curve.iloc[-1] if not portfolio_curve.empty else -np.inf)
            elif line.get_label() == "Abenomics Period": # Skip Abenomics Period from sorting
                final_values.append(-np.inf) # Place it at the bottom
            else:
                ticker_label = line.get_label().split(' ')[0] # Extract ticker from label
                if ticker_label in scaled.columns and not scaled[ticker_label].empty:
                    final_values.append(scaled[ticker_label].iloc[-1])
                else:
                    final_values.append(-np.inf) # Handle cases where data might be missing

        # Filter out Abenomics Period from sorting and re-add it later
        sorted_items = sorted([(val, line, label) for val, line, label in zip(final_values, lines, labels) if label != "Abenomics Period"], key=lambda item: item[0], reverse=True)
        sorted_lines = [item[1] for item in sorted_items]
        sorted_labels = [item[2] for item in sorted_items]

        # Add Abenomics Period back if it was present
        abenomics_handle = None
        abenomics_label = None
        for line, label in zip(lines, labels):
            if label == "Abenomics Period":
                abenomics_handle = line
                abenomics_label = label
                break
        if abenomics_handle and abenomics_label:
            sorted_lines.append(abenomics_handle)
            sorted_labels.append(abenomics_label)

        ax.set_title(str(year), fontsize=14, fontweight="bold")
        ax.set_ylabel("Indexed performance (base = 1)", fontsize=10) # Changed base from 100 to 1
        ax.grid(True, which="both", ls="-", alpha=0.5) # Ensure both major and minor grid lines
        ax.xaxis.set_major_locator(mdates.YearLocator()) # Changed to YearLocator
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y")) # Changed to display year only
        ax.tick_params(axis="x", rotation=30, labelsize=9)
        ax.tick_params(axis="y", labelsize=9)
        ax.legend(sorted_lines, sorted_labels, fontsize=10, ncol=1, frameon=True, loc='center left', bbox_to_anchor=(1, 0.5), facecolor="white", framealpha=1.0)

        # Hide x-axis labels for non-last subplots
        if i < len(full_year_range) - 1:
            ax.set_xlabel('')
            ax.tick_params(labelbottom=False)
        else:
            ax.set_xlabel("Date", fontsize=10)


    for ax in axes[len(full_year_range):]:
        fig.delaxes(ax)

    fig.suptitle("Portfolio Performance by Year", fontsize=18, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 0.92, 0.96)) # Adjusted rect for wider graph
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, format=output_path.suffix.lstrip("."), dpi=150)
    plt.close(fig)
    return output_path