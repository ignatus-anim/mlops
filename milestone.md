# Milestone Status – Continuous ML Pipeline

_Last updated: 14-Jul-2025_

This document maps the **requirements.md** guidelines to the current implementation, highlighting what has been completed and what is still outstanding.  Tasks are grouped by project phase and marked as **Done**, **In-Progress**, or **To-Do**.

---

## 1. Environment Setup
| Item | Status | Notes |
|------|--------|-------|
| Python ≥3.10 | **Done** | Using Python 3.11 in Docker images. |
| Workflow orchestration – Airflow | **Done** | Airflow 3.0.2 deployed via Docker-Compose. |
| Experiment tracking – MLflow | **Done** | MLflow server (Postgres backend, S3 artifacts) running on port 5000. |
| Containerisation – Docker | **Done** | All components containerised (Airflow stack, MLflow, Inference backend & frontend). |
| Model serving stack | **Done** | Flask backend (port 6001) with Nginx static frontend (port 6500). |
| Storage – S3 artifacts/datasets | **Done** | Bucket `mlops-bucket0982` configured; best-model stored under `best_model/`. |
| CI/CD, Monitoring, Versioning, K8s | **To-Do** | Not yet integrated. |

## 2. Automated Model Training & Validation
| Deliverable | Status | Notes |
|-------------|--------|-------|
| Data preprocessing & validation | **In-Progress** | Basic preprocessing in DAG; explicit validation checks still needed. |
| Recurring training jobs | **Done** | Airflow DAG schedules training; dynamic experiment naming. |
| Metric logging | **Done** | R², etc., logged to MLflow; best-model logic implemented. |
| Store trained model artifacts | **Done** | Saved to S3 & MLflow artifacts. |
| Unit tests for training | **To-Do** | No automated tests yet. |

## 3. A/B Testing Infrastructure
| Deliverable | Status | Notes |
|-------------|--------|-------|
| Traffic splitter / LB config | **To-Do** | Not implemented (using single model endpoint). |
| Logging live predictions & ground truth | **To-Do** | ─ |
| A/B performance comparison script | **To-Do** | ─ |

## 4. Automated Rollbacks
| Deliverable | Status | Notes |
|-------------|--------|-------|
| Threshold rules & rollback script | **To-Do** | No rollback automation yet. |
| Alerting (Slack / email) | **To-Do** | ─ |
| Deployment scripts with rollback | **To-Do** | ─ |

## 5. Inference API
| Requirement | Status | Notes |
|-------------|--------|-------|
| RESTful endpoints | **Done** | `/api/get_location_names`, `/api/predict_home_price`. |
| Health-check endpoint | **To-Do** | Add `/health` returning 200. |
| Batch predictions support | **To-Do** | Currently single-row only. |
| Dynamic model version loading | **Done** | Reads best model from S3 key prefix. |
| Observability / logging | **In-Progress** | Basic request logging; metrics not yet exported. |

## 6. Model Versioning & Experiment Tracking (Bonus)
| Deliverable | Status | Notes |
|-------------|--------|-------|
| MLflow tracking | **Done** | Experiments auto-created per run. |
| Model registry / promotion workflow | **To-Do** | Not yet leveraging MLflow Model Registry. |

## 7. Testing & Validation
| Test Type | Status | Notes |
|-----------|--------|-------|
| Unit tests (train, inference) | **To-Do** | Create pytest suite. |
| Integration tests (API) | **To-Do** | ─ |
| Load tests | **To-Do** | ─ |
| CI pipeline | **To-Do** | GitHub Actions not configured. |

## 8. Documentation & House-keeping
| Item | Status | Notes |
|------|--------|-------|
| README explaining run/deploy steps | **In-Progress** | Some docs in comments; need full README. |
| .gitignore | **Done** | Added comprehensive ignore rules. |
| requirements.txt / env files | **Done** | `.env` in place; Python deps managed inside Dockerfiles. |

---

## Next Milestones
1. **Testing & CI**  
   • Add pytest suite and GitHub Actions workflow for unit/integration tests.  
   • Include Docker build & security scan.
2. **A/B Testing & Rollback**  
   • Implement shadow deployment or traffic-splitting via Nginx / Envoy.  
   • Script to compare live metrics; rollback logic in Airflow DAG.
3. **Monitoring & Observability**  
   • Expose Prometheus metrics (model latency, error rates).  
   • Grafana dashboard.
4. **Model Registry & Promotion Flow**  
   • Use MLflow Model Registry; automate stage transitions.
5. **CI/CD to Kubernetes (optional)**  
   • Helm charts & GitOps promotion.

Feel free to adjust milestones or priorities based on team goals. Good progress so far—core training loop, experiment tracking, and basic inference service are operational. Remaining work mainly involves production-grade ops: testing, rollout strategy, monitoring, and CI/CD.  
