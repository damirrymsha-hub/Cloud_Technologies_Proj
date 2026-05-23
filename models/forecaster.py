"""
Cost forecaster using Facebook Prophet.

Prophet decomposes a time-series into trend + seasonality + holidays.
Cloud billing data typically exhibits weekly seasonality (lower weekend spend
for dev/staging workloads), making Prophet a strong fit even with only 90 days
of history — where classical ARIMA would struggle.

References
----------
Taylor, S. J., & Letham, B. (2018). Forecasting at Scale.  The American
Statistician, 72(1), 37-45.  https://doi.org/10.1080/00031305.2017.1380080
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd


@dataclass
class ForecastPoint:
    """One day of the Prophet output."""
    ds: str             # ISO date string
    yhat: float         # predicted daily total cost
    yhat_lower: float   # lower bound of 90 % confidence interval
    yhat_upper: float   # upper bound of 90 % confidence interval


class CostForecaster:
    """
    Wraps Facebook Prophet for 30/90-day cost forecasting.

    Usage
    -----
    forecaster = CostForecaster().fit(daily_df)
    points_30d = forecaster.forecast(horizon_days=30)
    points_90d = forecaster.forecast(horizon_days=90)
    """

    def __init__(self, changepoint_prior_scale: float = 0.05) -> None:
        """
        Parameters
        ----------
        changepoint_prior_scale : float
            Controls trend flexibility.  Lower values produce smoother trends;
            higher values allow sharper bends.  0.05 works well for cloud
            billing which drifts gradually rather than pivoting suddenly.
        """
        self._cps = changepoint_prior_scale
        self._model = None
        self._trained = False

    # ── Training ──────────────────────────────────────────────────────────────

    def fit(self, daily: pd.DataFrame) -> "CostForecaster":
        """
        Fit Prophet on a daily aggregate cost series.

        Parameters
        ----------
        daily : DataFrame
            Must have columns [ds, y] where ds is a datetime and y is the
            total daily cost across all resources in USD.  Prophet requires
            at least ~3 weeks of history to detect weekly seasonality.
        """
        from prophet import Prophet  # optional dependency; imported lazily

        self._model = Prophet(
            changepoint_prior_scale=self._cps,
            weekly_seasonality=True,
            yearly_seasonality=False,   # 90 days is too short for yearly cycles
            interval_width=0.90,        # 90 % confidence intervals
        )
        self._model.fit(daily)
        self._trained = True
        return self

    # ── Inference ─────────────────────────────────────────────────────────────

    def forecast(self, horizon_days: int = 30) -> List[ForecastPoint]:
        """
        Generate a forecast for the next horizon_days calendar days.

        Returns only future rows (beyond the end of the training data),
        so the list length equals horizon_days.
        """
        if not self._trained:
            raise RuntimeError("Call fit() before forecast().")

        future = self._model.make_future_dataframe(periods=horizon_days)
        pred = self._model.predict(future)

        future_pred = pred.tail(horizon_days)
        return [
            ForecastPoint(
                ds=str(row["ds"])[:10],
                yhat=round(float(row["yhat"]), 2),
                yhat_lower=round(float(row["yhat_lower"]), 2),
                yhat_upper=round(float(row["yhat_upper"]), 2),
            )
            for _, row in future_pred.iterrows()
        ]
