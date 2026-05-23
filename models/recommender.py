"""
Hybrid recommendation engine: deterministic rule layer → Random Forest classifier.

Architecture
------------
1. Rule layer  — applies hard thresholds to produce an action label for every
                 resource.  Covers clear-cut cases (chronically idle, severely
                 under-utilised, etc.).
2. ML layer    — a Random Forest is trained on the rule-generated labels.
                 It learns soft decision boundaries and can generalise to
                 resource profiles that fall between thresholds.

This hybrid design means the ML model always has labelled training data (from
the rule layer) and the rules remain interpretable for the university audience.

Actions
-------
downsize_instance   → switch to a smaller instance type
schedule_shutdown   → add on/off schedule (nights/weekends)
switch_to_reserved  → commit to 1-year Reserved Instance pricing (~35 % saving)
switch_to_spot      → use Spot/Preemptible for fault-tolerant workloads (~70 %)
no_action           → no cost-saving opportunity identified
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

# ── Constants ─────────────────────────────────────────────────────────────────

DOWNSIZE     = "downsize_instance"
SCHEDULE_OFF = "schedule_shutdown"
RESERVE      = "switch_to_reserved"
SPOT         = "switch_to_spot"
NO_ACTION    = "no_action"

# Estimated fraction of current monthly spend saved by each action
SAVINGS_RATE: dict[str, float] = {
    DOWNSIZE:     0.40,
    SCHEDULE_OFF: 0.30,
    RESERVE:      0.35,
    SPOT:         0.70,
    NO_ACTION:    0.00,
}

RISK_LEVEL: dict[str, str] = {
    DOWNSIZE:     "medium",
    SCHEDULE_OFF: "low",
    RESERVE:      "low",
    SPOT:         "high",
    NO_ACTION:    "low",
}

# Feature columns the Random Forest trains and predicts on
ML_FEATURES = [
    "cpu_mean", "cpu_p95", "cpu_waste_ratio",
    "mem_mean", "idle_day_pct", "avg_hours_running",
    "cost_mean_usd", "cost_std_usd", "cost_trend",
    "net_io_mean_gb",
]


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class Recommendation:
    """One cost-saving recommendation for a cloud resource."""
    resource_id: str
    instance_type: str
    environment: str
    action: str
    estimated_monthly_savings_usd: float
    confidence_score: float         # RF probability for the predicted class
    risk_level: str                 # "low" | "medium" | "high"
    reason: str                     # human-readable explanation


# ── Engine ────────────────────────────────────────────────────────────────────

class RecommendationEngine:
    """
    Two-layer recommender: rule-based labels → Random Forest classifier.

    Usage
    -----
    engine = RecommendationEngine().fit(features_df)
    recommendations = engine.recommend(features_df)
    """

    def __init__(self, random_state: int = 42) -> None:
        self._rf = RandomForestClassifier(
            n_estimators=200,
            max_depth=6,
            random_state=random_state,
            class_weight="balanced",  # prevents NO_ACTION from dominating
        )
        self._le = LabelEncoder()
        self._trained = False

    # ── Rule layer ────────────────────────────────────────────────────────────

    def _rule_label(self, row: pd.Series) -> str:
        """
        Apply deterministic business rules to select the best action.

        Rules are evaluated in priority order; the first match wins.

        idle_day_pct > 70 % AND avg run time < 12 h/day
            → scheduled shutdown saves money without performance risk

        cpu_mean < 5 % AND cpu_p95 < 15 %
            → instance is chronically under-utilised; downsize is safe

        cost coefficient of variation < 15 % AND env == prod
            → stable baseline workload; Reserved Instances offer ~35 % discount

        dev/staging env AND cpu_waste_ratio > 50 %
            → interruptible workload; Spot pricing gives the biggest saving
        """
        if row["idle_day_pct"] > 0.70 and row["avg_hours_running"] < 12.0:
            return SCHEDULE_OFF

        if row["cpu_mean"] < 5.0 and row["cpu_p95"] < 15.0:
            return DOWNSIZE

        cv = row["cost_std_usd"] / max(row["cost_mean_usd"], 0.01)
        if cv < 0.15 and row["environment"] == "prod":
            return RESERVE

        if row["environment"] in ("dev", "staging") and row["cpu_waste_ratio"] > 0.50:
            return SPOT

        return NO_ACTION

    # ── Training ──────────────────────────────────────────────────────────────

    def fit(self, features: pd.DataFrame) -> "RecommendationEngine":
        """
        Generate rule-based labels and train the Random Forest on them.

        The RF learns soft decision surfaces that generalise the hard rule
        thresholds, allowing it to catch borderline cases the rules would miss.
        """
        labels = features.apply(self._rule_label, axis=1)
        X = features[ML_FEATURES].fillna(0.0).values
        y = self._le.fit_transform(labels)
        self._rf.fit(X, y)
        self._trained = True
        return self

    # ── Inference ─────────────────────────────────────────────────────────────

    def recommend(self, features: pd.DataFrame) -> List[Recommendation]:
        """
        Produce one Recommendation per actionable resource.

        NO_ACTION resources are filtered out.  Results are sorted by
        estimated_monthly_savings_usd descending so the highest-value
        opportunities appear first.
        """
        if not self._trained:
            raise RuntimeError("Call fit() before recommend().")

        X = features[ML_FEATURES].fillna(0.0).values
        proba = self._rf.predict_proba(X)      # shape (n_resources, n_classes)
        pred_idx = proba.argmax(axis=1)
        confidence = proba.max(axis=1)
        actions = self._le.inverse_transform(pred_idx)

        recs: List[Recommendation] = []
        for i, row in features.reset_index(drop=True).iterrows():
            action = str(actions[i])
            if action == NO_ACTION:
                continue
            monthly_cost = float(row["cost_mean_usd"]) * 30.0
            savings = round(monthly_cost * SAVINGS_RATE.get(action, 0.0), 2)
            recs.append(Recommendation(
                resource_id=str(row["resource_id"]),
                instance_type=str(row["instance_type"]),
                environment=str(row["environment"]),
                action=action,
                estimated_monthly_savings_usd=savings,
                confidence_score=round(float(confidence[i]), 4),
                risk_level=RISK_LEVEL.get(action, "medium"),
                reason=_build_reason(action, row),
            ))

        return sorted(recs, key=lambda r: r.estimated_monthly_savings_usd, reverse=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_reason(action: str, row: pd.Series) -> str:
    """Return a human-readable explanation for a recommendation."""
    if action == DOWNSIZE:
        return (
            f"Average CPU {row['cpu_mean']:.1f}% (p95: {row['cpu_p95']:.1f}%) — "
            "well below instance capacity. Downsizing will maintain performance "
            "at significantly lower cost."
        )
    if action == SCHEDULE_OFF:
        return (
            f"Instance is idle {row['idle_day_pct']*100:.0f}% of days and runs "
            f"{row['avg_hours_running']:.1f} h/day on average. "
            "A scheduled shutdown during off-hours will eliminate idle spend."
        )
    if action == RESERVE:
        return (
            "Stable production workload with low cost variance. "
            "Switching to a 1-year Reserved Instance could save ~35%."
        )
    if action == SPOT:
        return (
            f"{row['environment'].capitalize()} environment with "
            f"{row['cpu_waste_ratio']*100:.0f}% CPU headroom. "
            "Spot/Preemptible instances are cost-effective for "
            "interruption-tolerant workloads."
        )
    return "No significant cost-saving opportunity identified."
