from __future__ import annotations

import math
from typing import Callable, Mapping

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from ..common.config import TRADING_DAYS


class PortfolioConstructionError(RuntimeError):
    """安全なポートフォリオ構築条件を満たさない場合に送出する。"""


def _annualize_return(daily_mean: float) -> float:
    return float(daily_mean * TRADING_DAYS)


def _annualize_volatility(daily_vol: float) -> float:
    return float(daily_vol * np.sqrt(TRADING_DAYS))


def _validate_parameters(max_weight: float, lookback_days: int, minimum: int) -> None:
    if not 0 < max_weight <= 1:
        raise ValueError("max_weight must be in (0, 1]")
    if lookback_days < 2:
        raise ValueError("lookback_days must be at least 2 trading observations")
    if minimum < 2:
        raise ValueError("min_training_observations must be at least 2")
    if minimum > lookback_days:
        raise ValueError(
            "min_training_observations cannot exceed lookback_days"
        )


def _select_training_returns(
    returns: pd.DataFrame,
    min_observations: int,
    max_weight: float,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """十分な観測数と共通取引日を持つ銘柄だけを選ぶ。

    欠損を含む銘柄を黙って補間しない。まず個別観測数で除外し、その後、
    共通取引日が最低観測数へ達するまで欠損の多い列を除外する。
    """

    if returns.empty:
        raise PortfolioConstructionError("training return window is empty")

    excluded: dict[str, str] = {}
    counts = returns.notna().sum()
    candidates = [
        ticker for ticker in returns.columns if counts[ticker] >= min_observations
    ]
    for ticker in returns.columns:
        if ticker not in candidates:
            excluded[ticker] = (
                f"insufficient_training_observations:{int(counts[ticker])}"
            )

    minimum_assets = math.ceil(1 / max_weight - 1e-12)
    if len(candidates) < minimum_assets:
        raise PortfolioConstructionError(
            "not enough eligible assets for the max_weight constraint: "
            f"eligible={len(candidates)}, required={minimum_assets}"
        )

    while len(candidates) >= minimum_assets:
        selected = returns.loc[:, candidates].dropna(how="any")
        if len(selected) >= min_observations:
            return selected, excluded

        missing = returns.loc[:, candidates].isna().sum()
        worst_missing = int(missing.max())
        worst = sorted(
            ticker for ticker in candidates if int(missing[ticker]) == worst_missing
        )[0]
        excluded[worst] = (
            "removed_to_restore_common_training_window:"
            f"missing={worst_missing}"
        )
        candidates.remove(worst)

    raise PortfolioConstructionError(
        "unable to form a complete training matrix without violating max_weight"
    )


def _weight_sharpe(returns: pd.DataFrame, max_weight: float) -> pd.Series:
    if returns.empty or returns.isna().any().any():
        raise PortfolioConstructionError(
            "optimizer requires a non-empty complete return matrix"
        )

    tickers = list(returns.columns)
    count = len(tickers)
    if count * max_weight < 1 - 1e-10:
        raise PortfolioConstructionError(
            "max_weight constraint is infeasible for the eligible asset count"
        )

    means = returns.mean().to_numpy(dtype=float)
    covariance = returns.cov().to_numpy(dtype=float)
    if not np.isfinite(means).all() or not np.isfinite(covariance).all():
        raise PortfolioConstructionError("training statistics contain non-finite values")

    def objective(weights: np.ndarray) -> float:
        portfolio_return = float(np.dot(weights, means) * TRADING_DAYS)
        variance = float(np.dot(weights, covariance).dot(weights) * TRADING_DAYS)
        if variance <= 1e-18:
            return 1e12
        return -portfolio_return / math.sqrt(variance)

    bounds = [(0.0, max_weight)] * count
    constraints = ({"type": "eq", "fun": lambda weights: np.sum(weights) - 1},)
    initial = np.full(count, 1 / count, dtype=float)
    result = minimize(
        objective,
        initial,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 2_000, "ftol": 1e-12},
    )

    if not result.success:
        raise PortfolioConstructionError(
            f"optimizer failed: status={result.status}, message={result.message}"
        )

    weights = np.asarray(result.x, dtype=float)
    weights[np.abs(weights) < 1e-12] = 0.0
    if not np.isfinite(weights).all():
        raise PortfolioConstructionError("optimizer returned non-finite weights")
    if abs(float(weights.sum()) - 1.0) > 1e-7:
        raise PortfolioConstructionError(
            f"optimizer weights do not sum to one: {weights.sum()}"
        )
    if float(weights.min()) < -1e-8 or float(weights.max()) > max_weight + 1e-8:
        raise PortfolioConstructionError(
            "optimizer result violates long-only or max_weight constraints"
        )

    return pd.Series(weights, index=tickers, dtype=float)


def _metrics(returns: pd.DataFrame, weights: pd.Series) -> dict[str, float | str | int]:
    active = weights[weights > 1e-10]
    if active.empty:
        raise PortfolioConstructionError("portfolio has no active positions")

    available = returns.loc[:, active.index].dropna(how="any")
    if available.empty:
        raise PortfolioConstructionError("evaluation window has no complete observations")

    daily = available.mul(active, axis=1).sum(axis=1)
    annual_return = _annualize_return(float(daily.mean()))
    volatility = _annualize_volatility(float(daily.std(ddof=0)))
    sharpe_ratio = 0.0 if volatility == 0 else annual_return / volatility
    curve = (1 + daily).cumprod()
    drawdown = (curve / curve.cummax()) - 1
    max_drawdown = float(drawdown.min())

    values = [annual_return, volatility, sharpe_ratio, max_drawdown]
    if not all(math.isfinite(value) for value in values):
        raise PortfolioConstructionError("evaluation metrics contain non-finite values")

    return {
        "annual_return": annual_return,
        "annual_return_method": "arithmetic_daily_mean_x_252",
        "volatility": volatility,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "evaluation_observations": int(len(available)),
    }


def _weight_entries(
    weights: pd.Series,
    names: Mapping[str, str],
    requested_tickers: list[str],
) -> dict[str, dict[str, float | str]]:
    return {
        ticker: {
            "name": names.get(ticker, ""),
            "weight": float(weights.get(ticker, 0.0)),
        }
        for ticker in requested_tickers
    }


def build_yearly_portfolios(
    frames: Mapping[str, pd.DataFrame],
    years,
    max_weight: float,
    lookback_days: int,
    min_training_observations: int,
    universe_resolver: Callable[[int], Mapping[str, str]],
    fallback_names: Mapping[str, str],
):
    """前年までの取引日だけで重みを決め、当年をOOS評価する。"""

    _validate_parameters(max_weight, lookback_days, min_training_observations)
    if not frames:
        raise PortfolioConstructionError("no price frames were supplied")

    closes = pd.DataFrame(
        {
            ticker: frame["close"]
            for ticker, frame in frames.items()
            if "close" in frame.columns
        }
    ).sort_index()
    if closes.empty:
        raise PortfolioConstructionError("no close-price series were supplied")

    returns = closes.pct_change(fill_method=None)
    results = {}
    timezone = returns.index.tz

    for year in years:
        universe = dict(universe_resolver(year))
        requested_tickers = [
            ticker for ticker in universe if ticker in returns.columns
        ]
        if not requested_tickers:
            raise PortfolioConstructionError(
                f"{year}: no universe members have price columns"
            )

        start = pd.Timestamp(year=year, month=1, day=1, tz=timezone)
        end = pd.Timestamp(year=year, month=12, day=31, tz=timezone)

        # 252は暦日ではなく、startより前に実在する252取引観測を意味する。
        prior_returns = returns.loc[returns.index < start, requested_tickers]
        training_window = prior_returns.tail(lookback_days)
        selected_training, excluded = _select_training_returns(
            training_window,
            min_training_observations,
            max_weight,
        )
        weights = _weight_sharpe(selected_training, max_weight)

        year_mask = (returns.index >= start) & (returns.index <= end)
        year_returns = returns.loc[year_mask, requested_tickers]
        metrics = _metrics(year_returns, weights)

        training_start = selected_training.index.min()
        training_end = selected_training.index.max()
        active_evaluation = year_returns.loc[:, weights.index].dropna(how="any")
        evaluation_start = active_evaluation.index.min()
        evaluation_end = active_evaluation.index.max()

        results[year] = {
            "status": "accepted",
            "period": {"start": f"{year}-01-01", "end": f"{year}-12-31"},
            "universe": [
                {
                    "ticker": ticker,
                    "name": universe.get(ticker, fallback_names.get(ticker, "")),
                }
                for ticker in requested_tickers
            ],
            "data_quality": {
                "requested_assets": len(requested_tickers),
                "eligible_assets": len(weights),
                "excluded_assets": excluded,
                "lookback_unit": "trading_observations",
                "lookback_observations": int(len(training_window)),
                "complete_training_observations": int(len(selected_training)),
                "snapshot_provenance_verified": False,
                "snapshot_warning": (
                    "Membership YAML must be independently verified against an "
                    "as-of source; price availability alone cannot prove index membership."
                ),
            },
            "portfolio": {
                "weights": _weight_entries(
                    weights,
                    {**fallback_names, **universe},
                    requested_tickers,
                ),
                "risk_metrics": metrics,
                "training_window": {
                    "start": training_start.isoformat(),
                    "end": training_end.isoformat(),
                },
                "evaluation_window": {
                    "start": evaluation_start.isoformat(),
                    "end": evaluation_end.isoformat(),
                },
            },
        }

    return results
