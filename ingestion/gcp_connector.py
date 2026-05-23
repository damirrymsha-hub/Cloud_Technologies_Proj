"""
GCP Billing Export connector.

Reads from a BigQuery billing export table when USE_REAL_CLOUD=true.
Falls back to the local mock CSV otherwise.

Prerequisites for real cloud mode
----------------------------------
1. Enable the BigQuery API in your GCP project.
2. Export billing data to BigQuery (GCP Console → Billing → Billing export).
3. Set environment variables:
     GCP_PROJECT_ID=my-project
     GCP_BILLING_DATASET=billing_export.gcp_billing_export_v1_<account_id>
4. Authenticate: gcloud auth application-default login
"""

from __future__ import annotations

import os
from datetime import date
from typing import Optional

import pandas as pd


class GCPConnector:
    """
    Reads GCP billing data from a BigQuery billing export table.

    Set USE_REAL_CLOUD=true and supply GCP_PROJECT_ID / GCP_BILLING_DATASET
    to query live data.
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        dataset: Optional[str] = None,
    ) -> None:
        self._use_real = os.getenv("USE_REAL_CLOUD", "false").lower() == "true"
        self._project_id = project_id or os.getenv("GCP_PROJECT_ID")
        self._dataset = dataset or os.getenv(
            "GCP_BILLING_DATASET",
            "billing_export.gcp_billing_export_v1",
        )
        if self._use_real:
            from google.cloud import bigquery  # only required when USE_REAL_CLOUD is set
            self._client = bigquery.Client(project=self._project_id)

    # ── Public ────────────────────────────────────────────────────────────────

    def fetch_daily_costs(self, start: date, end: date) -> pd.DataFrame:
        """
        Return a DataFrame with columns [date, resource_id, service, daily_cost_usd].

        Queries BigQuery when USE_REAL_CLOUD=true, otherwise loads mock CSV.
        """
        if not self._use_real:
            return self._load_mock(start, end)
        return self._query_bigquery(start, end)

    # ── Private ───────────────────────────────────────────────────────────────

    def _query_bigquery(self, start: date, end: date) -> pd.DataFrame:
        """Run a parameterised BigQuery query against the billing export table."""
        query = f"""
        SELECT
            DATE(usage_start_time)      AS date,
            resource.name               AS resource_id,
            service.description         AS service,
            SUM(cost)                   AS daily_cost_usd
        FROM `{self._dataset}`
        WHERE DATE(usage_start_time) BETWEEN '{start}' AND '{end}'
        GROUP BY 1, 2, 3
        ORDER BY 1
        """
        return self._client.query(query).to_dataframe()

    def _load_mock(self, start: date, end: date) -> pd.DataFrame:
        """Load the pre-generated mock CSV and filter to [start, end]."""
        mock_path = os.path.join(os.path.dirname(__file__), "..", "data", "sample_data.csv")
        df = pd.read_csv(mock_path, parse_dates=["date"])
        mask = (df["date"].dt.date >= start) & (df["date"].dt.date <= end)
        return df.loc[mask, ["date", "resource_id", "instance_type", "daily_cost_usd"]].copy()
