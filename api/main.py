"""
FastAPI backend for the Cloud Cost Optimizer.

All models are trained once at startup and cached in memory.
Endpoints are read-only: the application never writes to a database.

Routes
------
GET /health           liveness probe
GET /summary          30-day KPIs + top 3 recommendations
GET /recommendations  paginated, filtered list of recommendations
GET /forecast         30-day or 90-day cost forecast (Prophet)
GET /anomalies        detected cost spikes over the last 90 days
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from datetime import timedelta
from functools import lru_cache
from typing import List, Literal, Optional

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure the project root is on sys.path when running from the api/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.mock_generator import generate_dataset
from features.engineer import compute_daily_aggregates, compute_resource_features
from models.anomaly_detector import AnomalyDetector
from models.forecaster import CostForecaster
from models.recommender import Recommendation, RecommendationEngine


# ── Bootstrap ─────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_models():
    """
    Generate mock data and train all three models.

    lru_cache ensures this runs exactly once per process lifetime.
    Returns a tuple (df, features, daily, detector, forecaster, engine).
    """
    df = generate_dataset()
    features = compute_resource_features(df)
    daily = compute_daily_aggregates(df)

    detector   = AnomalyDetector(contamination=0.05).fit(df)
    forecaster = CostForecaster().fit(daily)
    engine     = RecommendationEngine().fit(features)

    return df, features, daily, detector, forecaster, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm up models on startup so the first request is not slow."""
    _load_models()
    yield


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Cloud Cost Optimizer",
    version="1.0.0",
    description="AI-powered cloud cost analysis, anomaly detection, forecasting, and recommendations.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Response schemas ──────────────────────────────────────────────────────────

class RecommendationOut(BaseModel):
    resource_id: str
    instance_type: str
    environment: str
    action: str
    estimated_monthly_savings_usd: float
    confidence_score: float
    risk_level: str
    reason: str


class AnomalyOut(BaseModel):
    date: str
    resource_id: str
    expected_cost: float
    actual_cost: float
    severity: float
    severity_label: str


class ForecastPointOut(BaseModel):
    ds: str
    yhat: float
    yhat_lower: float
    yhat_upper: float


class SummaryOut(BaseModel):
    total_cost_last_30d: float
    projected_monthly_savings_usd: float
    savings_pct: float
    num_recommendations: int
    top_recommendations: List[RecommendationOut]
    period_start: str
    period_end: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health", tags=["ops"])
def health():
    """Liveness probe used by Docker health checks and load balancers."""
    return {"status": "ok"}


@app.get("/summary", response_model=SummaryOut, tags=["analytics"])
def summary():
    """
    Return high-level cost metrics for the last 30 days.

    Includes total spend, projected savings, and the top 3 recommendations
    ranked by estimated monthly savings.
    """
    df, features, _, __, ___, engine = _load_models()

    cutoff = df["date"].max() - timedelta(days=30)
    last_30_cost = float(df[df["date"] >= cutoff]["daily_cost_usd"].sum())

    recs = engine.recommend(features)
    total_savings = sum(r.estimated_monthly_savings_usd for r in recs)
    savings_pct = (total_savings / last_30_cost * 100.0) if last_30_cost > 0 else 0.0

    return SummaryOut(
        total_cost_last_30d=round(last_30_cost, 2),
        projected_monthly_savings_usd=round(total_savings, 2),
        savings_pct=round(savings_pct, 1),
        num_recommendations=len(recs),
        top_recommendations=[_rec_out(r) for r in recs[:3]],
        period_start=str(cutoff.date()),
        period_end=str(df["date"].max().date()),
    )


@app.get("/recommendations", response_model=List[RecommendationOut], tags=["analytics"])
def recommendations(
    risk_level: Optional[Literal["low", "medium", "high"]] = Query(
        None, description="Filter by risk level"
    ),
    environment: Optional[str] = Query(
        None, description="Filter by environment (prod, dev, staging)"
    ),
    min_savings: float = Query(0.0, description="Minimum estimated monthly savings (USD)"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
):
    """
    Return a paginated, filtered list of recommendations sorted by estimated savings.

    All filter parameters are optional and combinable.
    """
    _, features, __, ___, ____, engine = _load_models()
    recs = engine.recommend(features)

    if risk_level:
        recs = [r for r in recs if r.risk_level == risk_level]
    if environment:
        recs = [r for r in recs if r.environment == environment]
    recs = [r for r in recs if r.estimated_monthly_savings_usd >= min_savings]

    start = (page - 1) * page_size
    return [_rec_out(r) for r in recs[start: start + page_size]]


@app.get("/forecast", tags=["analytics"])
def forecast(
    horizon: Literal[30, 90] = Query(30, description="Forecast horizon in days (30 or 90)"),
):
    """
    Return a Prophet cost forecast for the next 30 or 90 days.

    Response includes the predicted daily total cost (yhat) and 90 % confidence
    interval bounds (yhat_lower, yhat_upper).
    """
    _, __, ___, ____, forecaster, _____ = _load_models()
    points = forecaster.forecast(horizon_days=int(horizon))
    return {
        "horizon_days": horizon,
        "forecast": [
            ForecastPointOut(
                ds=p.ds,
                yhat=p.yhat,
                yhat_lower=p.yhat_lower,
                yhat_upper=p.yhat_upper,
            )
            for p in points
        ],
    }


@app.get("/anomalies", response_model=List[AnomalyOut], tags=["analytics"])
def anomalies():
    """
    Return all detected cost anomalies in the last 90 days.

    Sorted by severity descending (most anomalous first).
    Each entry includes the resource_id, date, expected vs actual cost, and
    a severity score in [0, 1].
    """
    df, _, __, detector, ___, ____ = _load_models()
    detected = detector.predict(df)
    return [
        AnomalyOut(
            date=a.date,
            resource_id=a.resource_id,
            expected_cost=a.expected_cost,
            actual_cost=a.actual_cost,
            severity=a.severity,
            severity_label=a.severity_label,
        )
        for a in detected
    ]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rec_out(r: Recommendation) -> RecommendationOut:
    """Convert an internal Recommendation dataclass to the Pydantic output model."""
    return RecommendationOut(
        resource_id=r.resource_id,
        instance_type=r.instance_type,
        environment=r.environment,
        action=r.action,
        estimated_monthly_savings_usd=r.estimated_monthly_savings_usd,
        confidence_score=r.confidence_score,
        risk_level=r.risk_level,
        reason=r.reason,
    )
