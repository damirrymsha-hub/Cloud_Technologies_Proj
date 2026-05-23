"""
Feature engineering for the Cloud Cost Optimizer.

Transforms raw daily billing/usage rows into per-resource feature vectors
that are consumed by the anomaly detector and the recommendation engine.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ── Public API ────────────────────────────────────────────────────────────────

def compute_resource_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate daily rows per resource_id into a single feature-vector DataFrame.

    Expected input columns
    ----------------------
    resource_id, date, daily_cost_usd, cpu_utilization_avg,
    memory_utilization_avg, network_io_gb, hours_running,
    instance_type, environment, region

    Returns one row per resource_id with the engineered features listed below.
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])

    grp = df.groupby("resource_id")

    # ── Cost features ─────────────────────────────────────────────────────────
    cost_grp = grp["daily_cost_usd"]
    cost_mean = cost_grp.mean()
    cost_std  = cost_grp.std().fillna(0.0)
    cost_total = cost_grp.sum()
    cost_trend = grp.apply(_linear_trend, include_groups=False)

    # ── CPU features ──────────────────────────────────────────────────────────
    cpu_mean = grp["cpu_utilization_avg"].mean()
    cpu_p95  = grp["cpu_utilization_avg"].quantile(0.95)
    cpu_waste_ratio = 1.0 - (cpu_mean / 100.0)

    # ── Memory ────────────────────────────────────────────────────────────────
    mem_mean = grp["memory_utilization_avg"].mean()

    # ── Idle detection ────────────────────────────────────────────────────────
    # idle_day_pct: fraction of days where average CPU < 5 %
    idle_day_pct = grp["cpu_utilization_avg"].apply(lambda s: (s < 5.0).mean())
    avg_hours    = grp["hours_running"].mean()

    # ── Network ───────────────────────────────────────────────────────────────
    net_io_mean = grp["network_io_gb"].mean()

    # ── Metadata (modal value of categorical columns) ─────────────────────────
    instance_type = grp["instance_type"].agg(lambda s: s.mode().iloc[0])
    environment   = grp["environment"].agg(lambda s: s.mode().iloc[0])
    region        = (
        grp["region"].agg(lambda s: s.mode().iloc[0])
        if "region" in df.columns
        else pd.Series("unknown", index=grp.groups.keys())
    )

    features = pd.DataFrame({
        "resource_id":      cost_mean.index,
        "cost_mean_usd":    cost_mean.values,
        "cost_std_usd":     cost_std.values,
        "cost_total_usd":   cost_total.values,
        "cost_trend":       cost_trend.values,
        "cpu_mean":         cpu_mean.values,
        "cpu_p95":          cpu_p95.values,
        "cpu_waste_ratio":  cpu_waste_ratio.values,
        "mem_mean":         mem_mean.values,
        "idle_day_pct":     idle_day_pct.values,
        "avg_hours_running":avg_hours.values,
        "net_io_mean_gb":   net_io_mean.values,
        "instance_type":    instance_type.values,
        "environment":      environment.values,
        "region":           region.values,
    })

    return features.reset_index(drop=True)


def compute_daily_aggregates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate all instances into a single daily total cost series.

    Returns a DataFrame with columns [ds, y] in the format expected by
    Facebook Prophet and the anomaly detector's time-series methods.
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    daily = (
        df.groupby("date")["daily_cost_usd"]
        .sum()
        .reset_index()
        .rename(columns={"date": "ds", "daily_cost_usd": "y"})
    )
    return daily.sort_values("ds").reset_index(drop=True)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _linear_trend(group: pd.DataFrame) -> float:
    """
    Compute the linear slope (USD/day) of daily_cost_usd over time.

    A positive slope means costs are growing; negative means they are shrinking.
    Returns 0.0 when there are fewer than 2 observations.
    """
    if "daily_cost_usd" not in group.columns or len(group) < 2:
        return 0.0
    y = group["daily_cost_usd"].values.astype(float)
    x = np.arange(len(y), dtype=float)
    return float(np.polyfit(x, y, 1)[0])
