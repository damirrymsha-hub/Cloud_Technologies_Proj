# Cloud Cost Optimizer

An AI-powered full-stack application that analyses cloud resource usage patterns,
detects billing anomalies, forecasts future spend, and recommends concrete
cost-saving actions — all without requiring real AWS or GCP credentials.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         Browser                              │
│           React + Recharts + Tailwind CSS (port 3000)        │
└─────────────────────────┬────────────────────────────────────┘
                          │  HTTP  /api/*
┌─────────────────────────▼────────────────────────────────────┐
│              FastAPI backend  (port 8000)                     │
│  /health  /summary  /recommendations  /forecast  /anomalies  │
└──────┬───────────────┬──────────────────┬────────────────────┘
       │               │                  │
┌──────▼──────┐  ┌─────▼──────┐  ┌───────▼─────────┐
│  Anomaly    │  │ Forecaster  │  │  Recommender    │
│  Detector   │  │  (Prophet)  │  │  (Rules + RF)   │
│ (Isolation  │  │             │  │                 │
│   Forest)   │  └─────────────┘  └─────────────────┘
└──────┬──────┘           │                │
       └──────────────────┴────────────────┘
                          │
              ┌───────────▼────────────┐
              │   Feature Engineering  │
              │   (features/engineer)  │
              └───────────┬────────────┘
                          │
              ┌───────────▼────────────┐
              │   Mock Data Generator  │  ← replaces real cloud APIs
              │   (data/mock_generator)│    when USE_REAL_CLOUD=false
              └────────────────────────┘
```

Data flows upward: the mock generator (or real cloud connectors) feeds raw
daily billing rows → feature engineering produces per-resource vectors →
three independent ML models operate on those vectors → FastAPI serves the
results → React renders them in the dashboard.

---

## ML Models

### 1. Anomaly Detector (`models/anomaly_detector.py`)

**Algorithm**: Isolation Forest (scikit-learn)

Isolation Forest is an *unsupervised* ensemble method that detects anomalies
by randomly partitioning the feature space.  Anomalous points (e.g., cost
spikes) are isolated in fewer splits and therefore receive a lower anomaly
score.

- **Features**: `daily_cost_usd`, `cpu_utilization_avg`, `memory_utilization_avg`
- **Contamination**: 5 % (expected fraction of outliers in training data)
- **Output**: list of `Anomaly` objects with `severity` in [0, 1] and a
  `severity_label` of `low / medium / high`

The raw `score_samples` output (lower = more anomalous) is linearly scaled to
[0, 1] so severity is interpretable without ML background.

### 2. Cost Forecaster (`models/forecaster.py`)

**Algorithm**: Facebook Prophet

Prophet decomposes the daily total cost time-series into:
- **Trend** — controlled by `changepoint_prior_scale=0.05` (smooth, gradual)
- **Weekly seasonality** — captures lower weekend spend for dev/staging

Training data: 90 days of daily aggregated cost.
Output: 30-day or 90-day forecasts with 90 % confidence intervals.

Weekly seasonality is enabled and yearly seasonality is disabled (90 days of
history is insufficient to estimate yearly patterns reliably).

### 3. Recommendation Engine (`models/recommender.py`)

**Algorithm**: Rule-based layer → Random Forest classifier

A two-stage hybrid:

1. **Rule layer** applies deterministic business thresholds to label every
   resource with an action (`downsize_instance`, `schedule_shutdown`,
   `switch_to_reserved`, `switch_to_spot`, `no_action`).
2. **Random Forest** is trained on those labels to learn *soft* decision
   boundaries — it generalises to resource profiles that fall between thresholds.

Because the RF is always supervised by the rules, the system is explainable
(each recommendation includes a `reason` string) while also benefiting from
learned generalisation.

Estimated savings are computed as a fixed percentage of the current monthly
spend per action type (40 % downsize, 35 % reserved, 30 % shutdown, 70 % spot).

---

## Project Structure

```
cloud-cost-optimizer/
├── data/
│   ├── mock_generator.py       # Synthetic AWS/GCP billing + usage data
│   └── sample_data.csv         # Generated on first run
├── ingestion/
│   ├── aws_connector.py        # AWS Cost Explorer (boto3) — optional
│   └── gcp_connector.py        # GCP BigQuery billing export — optional
├── features/
│   └── engineer.py             # Per-resource feature extraction
├── models/
│   ├── anomaly_detector.py     # Isolation Forest
│   ├── forecaster.py           # Prophet 30/90-day forecast
│   └── recommender.py          # Rules + Random Forest
├── api/
│   └── main.py                 # FastAPI: /summary /recommendations /forecast /anomalies
├── dashboard/
│   ├── src/
│   │   ├── App.jsx
│   │   └── components/
│   │       ├── CostChart.jsx
│   │       ├── RecommendationCard.jsx
│   │       ├── SavingsGauge.jsx
│   │       └── AnomalyTimeline.jsx
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile
├── notebooks/
│   └── exploration.ipynb       # EDA and model demos
├── tests/
│   ├── test_mock_generator.py
│   ├── test_anomaly_detector.py
│   └── test_recommender.py
├── .github/workflows/ci.yml   # Lint + test on every push
├── docker-compose.yml
├── Dockerfile.api
└── requirements.txt
```

---

## Quick Start

### Option A — Docker Compose (recommended)

```bash
# Clone / navigate to the project
cd cloud-cost-optimizer

# Build and start both services
docker-compose up --build

# API:       http://localhost:8000/docs
# Dashboard: http://localhost:3000
```

> First startup takes ~2–3 minutes while Prophet's CmdStan backend compiles.

### Option B — Local development

**Backend**

```bash
# Create a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# Generate the mock dataset
python data/mock_generator.py

# Start the API
uvicorn api.main:app --reload --port 8000
```

**Frontend** (separate terminal)

```bash
cd dashboard
npm install
npm run dev          # → http://localhost:3000
```

### Running tests

```bash
pytest tests/ -v
```

---

## Real Cloud Data (optional)

Set `USE_REAL_CLOUD=true` and configure credentials:

| Provider | Required setup |
|----------|---------------|
| AWS | Standard boto3 credentials (`~/.aws/credentials` or IAM role). Cost Explorer must be enabled in the AWS console. |
| GCP | `gcloud auth application-default login`. Set `GCP_PROJECT_ID` and `GCP_BILLING_DATASET` environment variables. BigQuery billing export must be configured. |

The connectors (`ingestion/aws_connector.py`, `ingestion/gcp_connector.py`) are
loaded lazily — the extra dependencies (`boto3`, `google-cloud-bigquery`) are
only needed when real cloud mode is enabled.

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness probe |
| `GET` | `/summary` | 30-day cost total, top 3 recommendations, savings % |
| `GET` | `/recommendations` | Paginated list; filter by `risk_level`, `environment`, `min_savings` |
| `GET` | `/forecast?horizon=30` | Prophet forecast (30 or 90 days) with confidence intervals |
| `GET` | `/anomalies` | Detected cost spikes for the last 90 days |

Interactive docs: `http://localhost:8000/docs`

---

## CI / CD

GitHub Actions runs on every push:

- **`python-tests`** — installs Python 3.11 dependencies, generates mock data, runs `pytest`
- **`eslint`** — installs Node 20 dependencies, runs ESLint on the dashboard source

See [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | Python 3.11, FastAPI, Uvicorn |
| ML | scikit-learn (Isolation Forest, Random Forest), Prophet |
| Data | pandas, NumPy, Faker |
| Frontend | React 18, Vite, Recharts, Tailwind CSS, Lucide Icons |
| Containerisation | Docker, Docker Compose, Nginx |
| CI | GitHub Actions |

---

## Limitations & Future Work

- **Simulated data only by default** — the mock generator produces realistic but
  entirely synthetic billing data.  Real patterns may differ significantly.
- **No persistent storage** — models are re-trained in memory on every restart.
  A production system would persist trained models to S3/GCS or a model registry.
- **Single-node** — the architecture is intentionally simple for a university
  demo.  At scale, model training would be an offline batch job.
- **Prophet startup time** — CmdStan compilation adds ~60 s to cold starts.
  In production, compile once and cache the binary.
