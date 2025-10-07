import numpy as np
import pandas as pd
from scipy.optimize import minimize

from ..common.config import TRADING_DAYS


def _annualize_return(daily_mean: float) -> float:
    return float(daily_mean * TRADING_DAYS)


def _annualize_volatility(daily_vol: float) -> float:
    return float(daily_vol * np.sqrt(TRADING_DAYS))


def _clean_training_returns(returns: pd.DataFrame) -> pd.DataFrame:

    cleaned = returns.dropna(axis=1, how="all")
    cleaned = cleaned.dropna(how="any")
    return cleaned


def _weight_sharpe(returns: pd.DataFrame, max_weight: float) -> pd.Series:
    cleaned = _clean_training_returns(returns)
    tickers = list(returns.columns)

    means = cleaned.mean().values
    cov = cleaned.cov().values
    count = len(means)

    def objective(weights):
        port_return = np.dot(weights, means) * TRADING_DAYS
        port_vol = np.sqrt(np.dot(weights, cov).dot(weights) * TRADING_DAYS)
        return 0 if port_vol == 0 else -port_return / port_vol

    bounds = [(0, max_weight)] * count
    constraints = ({"type": "eq", "fun": lambda w: np.sum(w) - 1},)
    initial = np.full(count, 1 / count)
    result = minimize(objective, initial, bounds=bounds, constraints=constraints)
    weights = result.x
    weights = np.clip(weights, 0, max_weight)
    weights = weights / weights.sum()

    series = pd.Series(0.0, index=tickers)
    for ticker, weight in zip(cleaned.columns, weights):
        series.loc[ticker] = weight
    return series


def _metrics(returns: pd.DataFrame, weights: pd.Series):
    available = returns.loc[:, weights.index].dropna()
    daily = available.dot(weights.loc[available.columns])
    annual_return = _annualize_return(float(daily.mean()))
    volatility = _annualize_volatility(float(daily.std(ddof=0)))
    sharpe_ratio = 0.0 if volatility == 0 else annual_return / volatility
    curve = (1 + daily).cumprod()
    drawdown = (curve / curve.cummax()) - 1
    max_drawdown = float(drawdown.min())
    return {
        "annual_return": annual_return,
        "volatility": volatility,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
    }


def _classification(weights, mapping):
    grouped = {}
    for ticker, weight in weights.items():
        key = mapping.get(ticker, "unclassified")
        grouped[key] = grouped.get(key, 0.0) + float(weight)
    return grouped


def _weight_entries(weights, names, tickers):
    return {
        ticker: {
            "name": names.get(ticker, ""),
            "weight": float(weights.get(ticker, 0.0)),
        }
        for ticker in tickers
    }


def build_yearly_portfolios(
    frames,
    years,
    max_weight,
    lookback_days,
    min_training_observations,
    universe_resolver,
    fallback_names,
):
    closes = pd.DataFrame({ticker: frame["close"] for ticker, frame in frames.items()})
    closes = closes.sort_index()
    returns = closes.pct_change(fill_method=None).dropna()
    results = {}
    tz = returns.index.tz
    for year in years:
        universe = universe_resolver(year)
        tickers = [ticker for ticker in universe if ticker in returns.columns]
        if not tickers:
            continue

        start = pd.Timestamp(year=year, month=1, day=1, tz=tz)
        end = pd.Timestamp(year=year, month=12, day=31, tz=tz)

        year_mask = (returns.index >= start) & (returns.index <= end)
        year_returns = returns.loc[year_mask, tickers]
        train_start = start - pd.Timedelta(days=lookback_days)
        train_mask = (returns.index >= train_start) & (returns.index < start)

        training_returns = returns.loc[train_mask, tickers]
        cleaned_training = _clean_training_returns(training_returns)

        weights = _weight_sharpe(training_returns, max_weight)
        metrics = _metrics(year_returns, weights)

        training_start = cleaned_training.index.min()
        training_end = cleaned_training.index.max()
        evaluation_start = year_returns.index.min()
        evaluation_end = year_returns.index.max()

        results[year] = {
            "period": {"start": f"{year}-01-01", "end": f"{year}-12-31"},
            "universe": [
                {
                    "ticker": ticker,
                    "name": universe.get(ticker, fallback_names.get(ticker, "")),
                }
                for ticker in tickers
            ],
            "portfolio": {
                "weights": _weight_entries(weights, {**fallback_names, **universe}, tickers),
                "risk_metrics": metrics,
                "training_window": {
                    "start": training_start.isoformat() if training_start is not None else None,
                    "end": training_end.isoformat() if training_end is not None else None,
                },
                "evaluation_window": {
                    "start": evaluation_start.isoformat() if evaluation_start is not None else None,
                    "end": evaluation_end.isoformat() if evaluation_end is not None else None,
                },
            },
        }
    return results
