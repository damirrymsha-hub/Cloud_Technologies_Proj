"""
Anomaly detector using Isolation Forest.

Isolation Forest isolates observations by randomly selecting a feature and a
random split value between that feature's min and max.  Anomalous points
(spikes) are isolated in fewer splits on average, yielding a lower anomaly
score.  We train on three signals per instance-day: cost, CPU, and memory.

References
----------
Liu, F. T., Ting, K. M., & Zhou, Z.-H. (2008). Isolation Forest. ICDM.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

FEATURE_COLS = ["daily_cost_usd", "cpu_utilization_avg", "memory_utilization_avg"]


@dataclass
class Anomaly:
    """One detected anomalous instance-day."""
    date: str
    resource_id: str
    expected_cost: float    # approximate per-resource daily average
    actual_cost: float
    severity: float         # 0–1, higher means more anomalous
    severity_label: str     # "low" | "medium" | "high"


class AnomalyDetector:
    """
    Wraps IsolationForest for point-anomaly detection on daily billing data.

    Usage
    -----
    detector = AnomalyDetector().fit(train_df)
    anomalies = detector.predict(test_df)
    """

    def __init__(self, contamination: float = 0.05, random_state: int = 42) -> None:
        """
        Parameters
        ----------
        contamination : float
            Expected proportion of anomalies in the training data (0, 0.5].
            0.05 → the detector flags roughly 5 % of points as anomalous.
        """
        self._iso = IsolationForest(
            n_estimators=200,
            contamination=contamination,
            random_state=random_state,
        )
        self._scaler = StandardScaler()
        self._trained = False
        self._cost_mean_per_resource: float = 0.0
        self._n_resources: int = 1

    # ── Training ──────────────────────────────────────────────────────────────

    def fit(self, df: pd.DataFrame) -> "AnomalyDetector":
        """
        Fit the detector on historical daily usage data.

        Parameters
        ----------
        df : DataFrame
            Must contain columns daily_cost_usd, cpu_utilization_avg,
            memory_utilization_avg.  Additional columns are ignored.
        """
        X = df[FEATURE_COLS].fillna(0.0).values
        X_scaled = self._scaler.fit_transform(X)
        self._iso.fit(X_scaled)
        self._trained = True
        self._cost_mean_per_resource = float(df["daily_cost_usd"].mean())
        self._n_resources = max(1, df["resource_id"].nunique())
        return self

    # ── Inference ─────────────────────────────────────────────────────────────

    def predict(self, df: pd.DataFrame) -> List[Anomaly]:
        """
        Identify anomalous rows in df and return a sorted list of Anomaly objects.

        IsolationForest returns -1 for anomalies and +1 for inliers.
        We map the raw score_samples output (negative, lower = more anomalous)
        to a [0, 1] severity scale where 1 is the most anomalous.

        Results are sorted by severity descending.
        """
        if not self._trained:
            raise RuntimeError("Call fit() before predict().")

        X = df[FEATURE_COLS].fillna(0.0).values
        X_scaled = self._scaler.transform(X)
        labels = self._iso.predict(X_scaled)       # -1 anomaly, +1 inlier
        raw_scores = self._iso.score_samples(X_scaled)  # lower → more anomalous

        # Normalise to [0, 1] where 1 = most anomalous
        s_min, s_max = raw_scores.min(), raw_scores.max()
        if s_max == s_min:
            severity = np.zeros_like(raw_scores)
        else:
            severity = (raw_scores - s_max) / (s_min - s_max)

        expected_per_resource = self._cost_mean_per_resource

        anomalies: List[Anomaly] = []
        for i, (label, sev) in enumerate(zip(labels, severity)):
            if label != -1:
                continue
            row = df.iloc[i]
            sev_label = (
                "high"   if sev > 0.70 else
                "medium" if sev > 0.40 else
                "low"
            )
            anomalies.append(Anomaly(
                date=str(row["date"])[:10],
                resource_id=str(row["resource_id"]),
                expected_cost=round(expected_per_resource, 4),
                actual_cost=round(float(row["daily_cost_usd"]), 4),
                severity=round(float(sev), 4),
                severity_label=sev_label,
            ))

        return sorted(anomalies, key=lambda a: a.severity, reverse=True)
