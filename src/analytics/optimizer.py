import numpy as np
import pandas as pd
from scipy.optimize import minimize


def _weight_sharpe(returns, max_weight):
    means = returns.mean().values
    cov = returns.cov().values
    count = len(means)
    def objective(weights):
        port_return = np.dot(weights, means) * 252
        port_vol = np.sqrt(np.dot(weights, cov).dot(weights) * 252)
        return 0 if port_vol == 0 else -port_return / port_vol
    bounds = [(0, max_weight)] * count
    constraints = ({"type": "eq", "fun": lambda w: np.sum(w) - 1},)
    initial = np.full(count, 1 / count)
    result = minimize(objective, initial, bounds=bounds, constraints=constraints)
    weights = result.x
    weights = np.clip(weights, 0, max_weight)
    weights = weights / weights.sum()
    return pd.Series(weights, index=returns.columns)


def _metrics(returns, weights):
    daily = returns.dot(weights)
    annual_return = float(daily.mean() * 252)
    volatility = float(daily.std(ddof=0) * np.sqrt(252))
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


def build_yearly_portfolios(frames, classification, years, max_weight, names):
    closes = pd.DataFrame({ticker: frame["close"] for ticker, frame in frames.items()})
    closes = closes.sort_index()
    returns = closes.pct_change().dropna()
    tickers = list(frames.keys())
    results = {}
    for year in years:
        year_returns = returns.loc[str(year)]
        if year_returns.empty:
            continue
        weights = _weight_sharpe(year_returns, max_weight)
        metrics = _metrics(year_returns, weights)
        classes = _classification(weights, classification)
        results[year] = {
            "period": {"start": f"{year}-01-01", "end": f"{year}-12-31"},
            "universe": [
                {
                    "ticker": ticker,
                    "name": names.get(ticker, ""),
                    "asset_class": classification.get(ticker, "unclassified"),
                }
                for ticker in tickers
            ],
            "portfolio": {
                "weights": _weight_entries(weights, names, tickers),
                "risk_metrics": metrics,
                "classification": classes,
            },
        }
    return results
