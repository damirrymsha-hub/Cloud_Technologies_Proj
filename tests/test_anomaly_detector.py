"""Tests for models/anomaly_detector.py."""

import pytest

from data.mock_generator import generate_dataset
from models.anomaly_detector import Anomaly, AnomalyDetector


@pytest.fixture(scope="module")
def fitted_detector():
    df = generate_dataset(num_instances=15, days=30)
    return AnomalyDetector(contamination=0.08, random_state=0).fit(df), df


def test_returns_list(fitted_detector):
    det, df = fitted_detector
    result = det.predict(df)
    assert isinstance(result, list)


def test_anomalies_are_dataclass_instances(fitted_detector):
    det, df = fitted_detector
    for a in det.predict(df):
        assert isinstance(a, Anomaly)


def test_severity_in_unit_interval(fitted_detector):
    det, df = fitted_detector
    for a in det.predict(df):
        assert 0.0 <= a.severity <= 1.0, f"severity {a.severity} out of range"


def test_severity_label_values(fitted_detector):
    det, df = fitted_detector
    valid = {"low", "medium", "high"}
    for a in det.predict(df):
        assert a.severity_label in valid


def test_sorted_by_severity_descending(fitted_detector):
    det, df = fitted_detector
    anomalies = det.predict(df)
    scores = [a.severity for a in anomalies]
    assert scores == sorted(scores, reverse=True)


def test_predict_before_fit_raises():
    det = AnomalyDetector()
    df = generate_dataset(num_instances=5, days=10)
    with pytest.raises(RuntimeError, match="fit"):
        det.predict(df)


def test_detector_finds_injected_spikes():
    """Injected spikes (3–8× base cost) should show up as anomalies."""
    df = generate_dataset(num_instances=20, days=90)
    det = AnomalyDetector(contamination=0.05).fit(df)
    anomalies = det.predict(df)
    assert len(anomalies) > 0
