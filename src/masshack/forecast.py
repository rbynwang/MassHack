"""Path 1 — LightGBM quantile forecaster for load and PV.

Trains a separate model for each target × quantile combination.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

try:
    import lightgbm as lgb
    _LGB_AVAILABLE = True
except ImportError:
    _LGB_AVAILABLE = False


FEATURE_COLS = [
    "hour_sin",
    "hour_cos",
    "dayofweek",
    "month",
    "demand_kw_lag1",
    "demand_kw_lag24",
    "pv_total_kw_lag1",
    "pv_total_kw_lag24",
    "temperature_c",
    "ghi_wm2",
]

TARGETS = ["demand_kw", "pv_total_kw"]
QUANTILES = [0.1, 0.5, 0.9]


@dataclass
class QuantileForecaster:
    """LightGBM quantile regression for load and PV over a 24-h horizon."""

    models: dict = field(default_factory=dict)  # key: (target, quantile)
    feature_cols: list[str] = field(default_factory=lambda: list(FEATURE_COLS))

    def fit(self, train_df: pd.DataFrame) -> "QuantileForecaster":
        """Fit one model per target × quantile."""
        if not _LGB_AVAILABLE:
            raise RuntimeError("lightgbm is not installed.")

        X = train_df[self.feature_cols].dropna()
        for target in TARGETS:
            y = train_df[target].loc[X.index]
            for q in QUANTILES:
                params = {
                    "objective": "quantile",
                    "alpha": q,
                    "n_estimators": 300,
                    "learning_rate": 0.05,
                    "num_leaves": 63,
                    "verbosity": -1,
                }
                model = lgb.LGBMRegressor(**params)
                model.fit(X, y)
                self.models[(target, q)] = model

        return self

    def predict(
        self,
        features: pd.DataFrame,
        quantile: float = 0.5,
    ) -> dict[str, np.ndarray]:
        """Return point (or quantile) forecasts for each target.

        Parameters
        ----------
        features : DataFrame with at least the feature columns.
        quantile : which quantile to return (must be in QUANTILES).
        """
        X = features[self.feature_cols]
        return {
            target: self.models[(target, quantile)].predict(X)
            for target in TARGETS
        }
