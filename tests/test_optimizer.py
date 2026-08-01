import unittest

import numpy as np
import pandas as pd

from src.analytics.optimizer import (
    PortfolioConstructionError,
    _metrics,
    _select_training_returns,
    _weight_sharpe,
)


class TrainingSelectionTests(unittest.TestCase):
    def test_insufficient_history_is_excluded(self) -> None:
        index = pd.date_range("2020-01-01", periods=10, freq="B", tz="Asia/Tokyo")
        returns = pd.DataFrame(
            {
                "A": np.linspace(0.001, 0.010, 10),
                "B": np.linspace(0.002, 0.011, 10),
                "C": [np.nan] * 7 + [0.001, 0.002, 0.003],
            },
            index=index,
        )
        selected, excluded = _select_training_returns(
            returns,
            min_observations=8,
            max_weight=0.5,
        )
        self.assertEqual(list(selected.columns), ["A", "B"])
        self.assertIn("C", excluded)

    def test_infeasible_max_weight_fails_closed(self) -> None:
        index = pd.date_range("2020-01-01", periods=10, freq="B")
        returns = pd.DataFrame(
            {"A": 0.001, "B": 0.002, "C": 0.003},
            index=index,
        )
        with self.assertRaises(PortfolioConstructionError):
            _select_training_returns(
                returns,
                min_observations=8,
                max_weight=0.2,
            )


class OptimizerTests(unittest.TestCase):
    def test_weights_respect_constraints(self) -> None:
        index = pd.date_range("2020-01-01", periods=80, freq="B")
        data = {
            f"T{i}": np.sin(np.arange(80) / (i + 2)) * 0.002 + 0.0003 * (i + 1)
            for i in range(5)
        }
        returns = pd.DataFrame(data, index=index)
        weights = _weight_sharpe(returns, max_weight=0.25)
        self.assertAlmostEqual(float(weights.sum()), 1.0, places=7)
        self.assertGreaterEqual(float(weights.min()), 0.0)
        self.assertLessEqual(float(weights.max()), 0.25 + 1e-8)

    def test_metrics_ignore_inactive_missing_asset(self) -> None:
        index = pd.date_range("2021-01-01", periods=20, freq="B")
        returns = pd.DataFrame(
            {
                "active": np.full(20, 0.001),
                "inactive": [np.nan] * 20,
            },
            index=index,
        )
        metrics = _metrics(
            returns,
            pd.Series({"active": 1.0, "inactive": 0.0}),
        )
        self.assertEqual(metrics["evaluation_observations"], 20)
        self.assertTrue(np.isfinite(metrics["annual_return"]))


if __name__ == "__main__":
    unittest.main()
