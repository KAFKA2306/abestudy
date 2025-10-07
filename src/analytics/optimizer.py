import numpy as np
import pandas as pd
from scipy.optimize import minimize

from ..common.config import TRADING_DAYS


def _clean(returns: pd.DataFrame) -> pd.DataFrame:
    if returns.empty:
        return returns
    return returns.dropna(axis=1, how="all").dropna(how="any")


def _sharpe_weights(returns: pd.DataFrame, max_weight: float) -> pd.Series:
    tickers = list(returns.columns)
    cleaned = _clean(returns)
    if cleaned.empty:
        return pd.Series(np.full(len(tickers), 1 / len(tickers)), index=tickers)

    means = cleaned.mean().values
    cov = cleaned.cov().values
    n_assets = len(means)
    bounds = [(0, max_weight)] * n_assets
    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1}
    start = np.full(n_assets, 1 / n_assets)

    def objective(weights: np.ndarray) -> float:
        port_return = float(weights @ means) * TRADING_DAYS
        port_vol = float(np.sqrt(weights @ cov @ weights) * np.sqrt(TRADING_DAYS))
        return 0.0 if port_vol == 0 else -port_return / port_vol

    result = minimize(objective, start, bounds=bounds, constraints=constraints)
    weights = result.x if result.success and not np.allclose(result.x.sum(), 0) else start
    weights = np.clip(weights, 0, max_weight)
    weights = weights / weights.sum()

    allocation = pd.Series(0.0, index=tickers)
    allocation.loc[cleaned.columns] = weights
    return allocation


def _metrics(returns: pd.DataFrame, weights: pd.Series) -> dict:
    aligned = returns.loc[:, weights.index].dropna()
    if aligned.empty:
        return {"annual_return": 0.0, "volatility": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0}

    portfolio = aligned @ weights.loc[aligned.columns]
    annual_return = float(portfolio.mean() * TRADING_DAYS)
    volatility = float(portfolio.std(ddof=0) * np.sqrt(TRADING_DAYS))
    sharpe_ratio = 0.0 if volatility == 0 else annual_return / volatility
    curve = (1 + portfolio).cumprod()
    drawdown = curve / curve.cummax() - 1
    return {
        "annual_return": annual_return,
        "volatility": volatility,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": float(drawdown.min()),
    }


def _entries(weights: pd.Series, names: dict, tickers: list[str]) -> dict:
    return {
        ticker: {"name": names.get(ticker, ""), "weight": float(weights.get(ticker, 0.0))}
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
    closes = pd.DataFrame({ticker: frame["close"] for ticker, frame in frames.items()}).sort_index()
    returns = closes.pct_change(fill_method=None).dropna()
    tz = returns.index.tz
    results = {}

    for year in years:
        universe = universe_resolver(year)
        tickers = [ticker for ticker in universe if ticker in returns.columns]
        if not tickers:
            continue

        start = pd.Timestamp(year=year, month=1, day=1, tz=tz)
        end = pd.Timestamp(year=year, month=12, day=31, tz=tz)
        evaluation = returns.loc[(returns.index >= start) & (returns.index <= end), tickers]
        if evaluation.empty:
            continue

        if lookback_days is None:
            training = returns.loc[returns.index < start, tickers]
        else:
            train_start = start - pd.Timedelta(days=lookback_days)
            training = returns.loc[(returns.index >= train_start) & (returns.index < start), tickers]

        cleaned_training = _clean(training)
        if cleaned_training.shape[0] < min_training_observations:
            continue

        weights = _sharpe_weights(training, max_weight)
        metrics = _metrics(evaluation, weights)
        names = {**fallback_names, **universe}

        results[year] = {
            "period": {"start": f"{year}-01-01", "end": f"{year}-12-31"},
            "universe": [
                {"ticker": ticker, "name": names.get(ticker, "")}
                for ticker in tickers
            ],
            "portfolio": {
                "weights": _entries(weights, names, tickers),
                "risk_metrics": metrics,
                "training_window": {
                    "start": cleaned_training.index.min().isoformat() if not cleaned_training.empty else None,
                    "end": cleaned_training.index.max().isoformat() if not cleaned_training.empty else None,
                },
                "evaluation_window": {
                    "start": evaluation.index.min().isoformat(),
                    "end": evaluation.index.max().isoformat(),
                },
            },
        }

    return results
