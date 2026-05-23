"""Tests for models/recommender.py."""

import pytest

from data.mock_generator import generate_dataset
from features.engineer import compute_resource_features
from models.recommender import Recommendation, RecommendationEngine


@pytest.fixture(scope="module")
def engine_and_features():
    df = generate_dataset(num_instances=20, days=30)
    features = compute_resource_features(df)
    engine = RecommendationEngine(random_state=0).fit(features)
    return engine, features


def test_returns_list(engine_and_features):
    engine, features = engine_and_features
    assert isinstance(engine.recommend(features), list)


def test_recommendation_type(engine_and_features):
    engine, features = engine_and_features
    for r in engine.recommend(features):
        assert isinstance(r, Recommendation)


def test_required_fields_present(engine_and_features):
    engine, features = engine_and_features
    for r in engine.recommend(features):
        assert r.resource_id
        assert r.action
        assert r.estimated_monthly_savings_usd >= 0.0
        assert 0.0 <= r.confidence_score <= 1.0
        assert r.risk_level in {"low", "medium", "high"}
        assert r.reason


def test_sorted_by_savings_descending(engine_and_features):
    engine, features = engine_and_features
    recs = engine.recommend(features)
    savings = [r.estimated_monthly_savings_usd for r in recs]
    assert savings == sorted(savings, reverse=True)


def test_no_action_resources_excluded(engine_and_features):
    engine, features = engine_and_features
    for r in engine.recommend(features):
        assert r.action != "no_action"


def test_valid_action_values(engine_and_features):
    engine, features = engine_and_features
    valid_actions = {
        "downsize_instance", "schedule_shutdown",
        "switch_to_reserved", "switch_to_spot",
    }
    for r in engine.recommend(features):
        assert r.action in valid_actions


def test_predict_before_fit_raises():
    engine = RecommendationEngine()
    df = generate_dataset(num_instances=5, days=10)
    features = compute_resource_features(df)
    with pytest.raises(RuntimeError, match="fit"):
        engine.recommend(features)
