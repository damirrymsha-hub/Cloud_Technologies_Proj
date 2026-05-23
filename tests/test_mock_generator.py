"""Tests for data/mock_generator.py."""

import pandas as pd
import pytest

from data.mock_generator import generate_dataset


@pytest.fixture(scope="module")
def small_df():
    """5 instances × 10 days — cheap enough to generate repeatedly."""
    return generate_dataset(num_instances=5, days=10)


def test_row_count(small_df):
    """Each instance should produce exactly one row per day."""
    assert len(small_df) == 5 * 10


def test_required_columns(small_df):
    expected = {
        "date", "resource_id", "instance_type", "region", "environment",
        "daily_cost_usd", "cpu_utilization_avg", "memory_utilization_avg",
        "network_io_gb", "hours_running",
    }
    assert expected.issubset(set(small_df.columns))


def test_no_negative_costs(small_df):
    assert (small_df["daily_cost_usd"] >= 0).all()


def test_cpu_in_valid_range(small_df):
    assert small_df["cpu_utilization_avg"].between(0, 100).all()


def test_memory_in_valid_range(small_df):
    assert small_df["memory_utilization_avg"].between(0, 100).all()


def test_hours_running_bounded(small_df):
    assert small_df["hours_running"].between(0, 24).all()


def test_environments_are_valid(small_df):
    assert set(small_df["environment"].unique()).issubset({"prod", "dev", "staging"})


def test_date_column_is_datetime(small_df):
    assert pd.api.types.is_datetime64_any_dtype(small_df["date"])


def test_cost_spikes_present():
    """Over 90 days the injected spikes should produce some outliers."""
    df = generate_dataset(num_instances=20, days=90)
    mean = df["daily_cost_usd"].mean()
    std = df["daily_cost_usd"].std()
    assert (df["daily_cost_usd"] > mean + 3 * std).any(), "Expected injected cost spikes"
