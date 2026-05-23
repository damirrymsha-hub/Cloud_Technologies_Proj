"""
AWS Cost Explorer connector.

Uses boto3 when USE_REAL_CLOUD=true; falls back to the local mock CSV otherwise
so the project runs without real AWS credentials or an internet connection.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Optional

import pandas as pd


class AWSConnector:
    """
    Thin wrapper around boto3's Cost Explorer API.

    Set the environment variable USE_REAL_CLOUD=true and configure standard
    AWS credential files / IAM roles to query real billing data.
    """

    def __init__(self, profile: Optional[str] = None) -> None:
        self._use_real = os.getenv("USE_REAL_CLOUD", "false").lower() == "true"
        if self._use_real:
            import boto3  # only required when USE_REAL_CLOUD is set
            session = boto3.Session(profile_name=profile)
            self._ce = session.client("ce", region_name="us-east-1")

    # ── Public ────────────────────────────────────────────────────────────────

    def fetch_daily_costs(self, start: date, end: date) -> pd.DataFrame:
        """
        Return a DataFrame with columns [date, resource_id, service, daily_cost_usd].

        Dates are inclusive on both ends.  When USE_REAL_CLOUD is false, loads
        the mock CSV and filters to the requested date range.
        """
        if not self._use_real:
            return self._load_mock(start, end)
        return self._query_cost_explorer(start, end)

    # ── Private ───────────────────────────────────────────────────────────────

    def _query_cost_explorer(self, start: date, end: date) -> pd.DataFrame:
        """Query AWS Cost Explorer and normalise the response into a flat DataFrame."""
        resp = self._ce.get_cost_and_usage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "RESOURCE_ID"}],
        )
        rows = []
        for result in resp["ResultsByTime"]:
            dt = result["TimePeriod"]["Start"]
            for group in result["Groups"]:
                rows.append({
                    "date": dt,
                    "resource_id": group["Keys"][0],
                    "service": "EC2",
                    "daily_cost_usd": float(group["Metrics"]["UnblendedCost"]["Amount"]),
                })
        return pd.DataFrame(rows)

    def _load_mock(self, start: date, end: date) -> pd.DataFrame:
        """Load the pre-generated mock CSV and filter to [start, end]."""
        mock_path = os.path.join(os.path.dirname(__file__), "..", "data", "sample_data.csv")
        df = pd.read_csv(mock_path, parse_dates=["date"])
        mask = (df["date"].dt.date >= start) & (df["date"].dt.date <= end)
        return df.loc[mask, ["date", "resource_id", "instance_type", "daily_cost_usd"]].copy()
