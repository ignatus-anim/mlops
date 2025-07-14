# Bangalore Home-Prices – End-to-End MLOps Pipeline

This repository demonstrates a production-style MLOps setup for continuous training, experiment tracking, A/B testing and automated rollbacks using **Apache Airflow**, **MLflow**, **Docker-Compose** and **AWS S3**.

## Current Architecture

```text
┌─────────────────────────┐        ┌───────────────┐
│      Airflow DAGs       │        │     MLflow    │
│  (training + evaluate)  │◀──────▶│ Postgres + S3 │
└─────────────────────────┘        └───────────────┘
          ▲                                   ▲
          │                                   │
          │         model artefacts           │
          ▼                                   │
┌─────────────────────────┐        │
│   S3  (mlops-bucket)    │◀───────┘
└─────────────────────────┘
          ▲
          │ best_model/ | candidate_model/
          │
┌────────────────────────────────────────────────────┐
│         Inference Layer (Docker)                  │
│ ┌───────────────┐ 80%  ┌───────────────┐          │
│ │  infer-prod   │◀────▶│  infer-cand   │          │
│ │ (6001)        │      │ (6002)        │          │
│ └───────────────┘      └───────────────┘          │
│        ▲                   ▲                      │
│        │ Nginx split       │                      │
│        └─────── router (7000) ─────────────────────┘
                 ▲
                 │
           Frontend (6500)
```

### Components
| Component | Purpose |
|-----------|---------|
| **Airflow 3.0.2** | Orchestrates training DAG and `evaluate_ab_dag` (promotion/rollback). |
| **MLflow Server** | Experiment tracking with Postgres backend and S3 artifact store. |
| **S3 (mlops-bucket0982)** | Stores raw data, experiment artifacts, and model folders `best_model/`, `candidate_model/`. |
| **Inference Backends** | Two Flask containers loading model based on `MODEL_PREFIX`. Each request is logged to Postgres (`prediction_logs`). |
| **Nginx Router** | Splits traffic 80/20 between prod and candidate. Exposed on port 7000 and used by the frontend. |
| **Static Frontend** | Bootstrap page for predictions, served by Nginx on 6500. |

## Quick Start

```bash
# 1. Build and start core stack (Airflow, MLflow, Postgres, etc.)
docker compose up -d   # uses docker-compose.yaml

# 2. Build / run A-B stack
export MLFLOW_S3_BUCKET=mlops-bucket0982

docker compose -f docker-compose.yaml -f docker-compose.ab.yml up -d --build router infer-prod infer-cand

# 3. Frontend (static)
docker compose up -d frontend   # or docker run −p 6500:6500 home-price-ui

# 4. Open URLs
- MLflow UI……… http://localhost:5000
- Airflow UI…… http://localhost:8080  (user:airflow / pw:airflow by default)
- Frontend………. http://localhost:6500  (talks to router on 7000)
```

## How A/B Testing Works
1. **Model Upload**  
   • Production model lives under `best_model/` in S3.  
   • Push a candidate model (`banglore_home_prices_model.pickle` + `columns.json`) to `candidate_model/`.

2. **Traffic Split**  
   • Nginx routes 20 % of `/api/*` requests to `infer-cand`, 80 % to `infer-prod`.

3. **Logging**  
   • Each backend writes a row to `prediction_logs` table with variant, inputs and prediction.

4. **Evaluation DAG**  
   • `evaluate_ab_dag` runs hourly. If `candidate_model` received ≥100 requests in the past 24 h, the DAG promotes:
     1. Copies files from `candidate_model/` → `best_model/` in S3.
     2. Restarts `infer-prod` so it loads the new artefacts.

5. **Rollback**  
   • Custom rules (metric thresholds) can be added to the DAG; currently only promotion threshold is implemented.

## Directory Guide
```
dags/                Airflow DAGs (train_model, evaluate_ab_dag)
inference/
  backend/           Flask API + model logic
  frontend/          Static UI (index.html, main.js, Dockerfile)
router/nginx.conf    Traffic-split configuration
milestone.md         Progress tracker
requirements.md      Original project guidelines
```

## Next Milestones
• Add unit/integration tests & GitHub Actions CI.  
• Extend evaluation DAG with real metrics (MAE, R²) once ground-truth feedback is available.  
• Slack/email notifications on promotion/rollback.  
• Grafana/Prometheus monitoring.  
• Optional: move to Kubernetes with Helm charts.
