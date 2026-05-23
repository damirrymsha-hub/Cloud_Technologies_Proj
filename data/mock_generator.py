"""
Mock data generator for the Cloud Cost Optimizer.

Produces realistic synthetic AWS/GCP billing and usage data for ~50 VM instances
over a 90-day window. Includes weekday/weekend patterns, idle dev instances, and
injected cost spikes — all without real cloud credentials.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from faker import Faker

fake = Faker()
rng = np.random.default_rng(42)

# ── Instance catalog ──────────────────────────────────────────────────────────

INSTANCE_TYPES: dict[str, dict] = {
    "t3.micro":   {"vcpu": 2,  "ram_gb": 1,  "base_hourly_usd": 0.0104},
    "t3.medium":  {"vcpu": 2,  "ram_gb": 4,  "base_hourly_usd": 0.0416},
    "t3.large":   {"vcpu": 2,  "ram_gb": 8,  "base_hourly_usd": 0.0832},
    "m5.large":   {"vcpu": 2,  "ram_gb": 8,  "base_hourly_usd": 0.0960},
    "m5.xlarge":  {"vcpu": 4,  "ram_gb": 16, "base_hourly_usd": 0.1920},
    "c5.xlarge":  {"vcpu": 4,  "ram_gb": 8,  "base_hourly_usd": 0.1700},
    "c5.2xlarge": {"vcpu": 8,  "ram_gb": 16, "base_hourly_usd": 0.3400},
    "r5.large":   {"vcpu": 2,  "ram_gb": 16, "base_hourly_usd": 0.1260},
}

REGIONS = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]
ENVIRONMENTS = ["prod", "dev", "staging"]
ENV_WEIGHTS = [0.4, 0.4, 0.2]

NUM_INSTANCES = 50
DAYS = 90


# ── Internal helpers ──────────────────────────────────────────────────────────

def _make_instance_catalog(n: int) -> pd.DataFrame:
    """Create a stable catalog of n simulated VM instances with fixed attributes."""
    itype_keys = list(INSTANCE_TYPES.keys())
    records = []
    for _ in range(n):
        env = str(rng.choice(ENVIRONMENTS, p=ENV_WEIGHTS))
        itype = str(rng.choice(itype_keys))
        records.append({
            "resource_id": f"i-{fake.hexify(text='^^^^^^^^')}",
            "instance_type": itype,
            "region": str(rng.choice(REGIONS)),
            "environment": env,
            "base_hourly_usd": INSTANCE_TYPES[itype]["base_hourly_usd"],
            # ~35 % of dev instances are chronically under-utilised
            "is_idle": (env == "dev") and (rng.random() < 0.35),
        })
    return pd.DataFrame(records)


def _daily_cpu(env: str, is_idle: bool, dow: int) -> float:
    """
    Return a realistic CPU utilisation percentage for one instance-day.

    Weekend traffic (dow >= 5) is dampened to reflect real-world workload patterns.
    """
    weekend = dow >= 5
    if is_idle:
        base = rng.uniform(1.0, 6.0)
    elif env == "prod":
        base = rng.uniform(25.0, 70.0) * (0.70 if weekend else 1.0)
    elif env == "staging":
        base = rng.uniform(10.0, 40.0) * (0.50 if weekend else 1.0)
    else:  # dev
        base = rng.uniform(5.0, 30.0) * (0.30 if weekend else 1.0)
    return float(np.clip(base + rng.normal(0, 3), 0.5, 99.5))


def _daily_memory(cpu: float) -> float:
    """Memory utilisation is loosely correlated with CPU but with higher variance."""
    return float(np.clip(cpu * rng.uniform(0.6, 1.4) + rng.normal(5, 5), 1.0, 99.0))


# ── Public API ────────────────────────────────────────────────────────────────

def generate_dataset(
    num_instances: int = NUM_INSTANCES,
    days: int = DAYS,
) -> pd.DataFrame:
    """
    Generate a synthetic daily billing + usage dataset.

    Returns a DataFrame with one row per (instance, day) covering `days` days
    of history ending yesterday.  Introduces realistic cost spikes on ~2 % of
    days per instance so the anomaly detector has signal to find.

    Columns
    -------
    date, resource_id, instance_type, region, environment,
    daily_cost_usd, cpu_utilization_avg, memory_utilization_avg,
    network_io_gb, hours_running
    """
    catalog = _make_instance_catalog(num_instances)
    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=days - 1)
    dates = [start_date + timedelta(days=d) for d in range(days)]

    rows = []
    for _, inst in catalog.iterrows():
        spike_days = set(
            rng.choice(days, size=max(1, days // 50), replace=False).tolist()
        )

        for d_idx, dt in enumerate(dates):
            dow = dt.weekday()
            cpu = _daily_cpu(inst["environment"], bool(inst["is_idle"]), dow)
            mem = _daily_memory(cpu)

            # Idle/dev instances run fewer hours on weekends
            if inst["is_idle"] and dow >= 5:
                hours_running = float(rng.uniform(0.0, 4.0))
            elif inst["environment"] == "dev" and dow >= 5:
                hours_running = float(rng.uniform(2.0, 12.0))
            else:
                hours_running = 24.0

            cost = float(inst["base_hourly_usd"]) * hours_running * rng.uniform(0.9, 1.1)

            if d_idx in spike_days:
                cost *= rng.uniform(3.0, 8.0)   # inject a realistic spike

            net_io = float(
                np.clip(rng.exponential(scale=max(0.5, cpu / 20.0)), 0.01, 500.0)
            )

            rows.append({
                "date": dt.isoformat(),
                "resource_id": inst["resource_id"],
                "instance_type": inst["instance_type"],
                "region": inst["region"],
                "environment": inst["environment"],
                "daily_cost_usd": round(float(cost), 4),
                "cpu_utilization_avg": round(float(cpu), 2),
                "memory_utilization_avg": round(float(mem), 2),
                "network_io_gb": round(float(net_io), 3),
                "hours_running": round(float(hours_running), 1),
            })

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["resource_id", "date"]).reset_index(drop=True)


if __name__ == "__main__":
    out_path = os.path.join(os.path.dirname(__file__), "sample_data.csv")
    df = generate_dataset()
    df.to_csv(out_path, index=False)
    print(f"Generated {len(df):,} rows  →  {out_path}")
    print(df.describe(include="all").T.to_string())
