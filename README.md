# Bangalore Home-Prices – End-to-End MLOps Pipeline

[![Tests](https://github.com/your-repo/actions/workflows/deploy.yml/badge.svg)](https://github.com/your-repo/actions/workflows/deploy.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-compose-blue.svg)](https://docs.docker.com/compose/)

A **production-ready MLOps pipeline** demonstrating continuous training, A/B testing, and automated rollbacks for machine learning models. Built with **Apache Airflow**, **MLflow**, **Docker**, and **AWS S3**.

## 🎯 Project Overview

**Problem**: Deploy ML models safely in production with continuous improvement and automated quality control.

**Solution**: Complete end-to-end pipeline featuring:
- ✅ **Automated Training** - Scheduled model training with experiment tracking
- ✅ **A/B Testing** - Traffic splitting between production and candidate models
- ✅ **Automated Rollbacks** - Performance-based promotion/rollback decisions
- ✅ **Drift Detection** - Statistical monitoring of data distribution changes
- ✅ **Comprehensive Testing** - 100% test coverage with CI/CD integration
- ✅ **Production Monitoring** - Prometheus + Grafana observability stack

## 🏗️ Architecture

```text
┌─────────────────────────┐        ┌───────────────┐
│      Airflow DAGs       │        │     MLflow    │
│  (training + evaluate)  │◀──────▶│ Postgres + S3 │
└─────────────────────────┘        └───────────────┘
          ▲                                   ▲
          │         model artifacts           │
          ▼                                   │
┌─────────────────────────┐        │
│   S3  (mlops-bucket)    │◀───────┘
└─────────────────────────┘
          ▲
          │ BO{n}/ | CO{n}/ (versioned models)
          │
┌────────────────────────────────────────────────────┐
│         Inference Layer (Docker)                  │
│ ┌───────────────┐ 80%  ┌───────────────┐          │
│ │  infer-prod   │◀────▶│  infer-cand   │          │
│ │ (6001)        │      │ (6002)        │          │
│ └───────────────┘      └───────────────┘          │
│        ▲                   ▲                      │
│        │ Nginx Router      │                      │
│        └─────── (7000) ────────────────────────────┘
                 ▲
                 │
    ┌─────────────────────────┐
    │ Frontend + Monitoring   │
    │ (6500) + Grafana (3000) │
    └─────────────────────────┘
```

## 🛠️ Technology Stack

| Component | Technology | Purpose |
|-----------|------------|----------|
| **Orchestration** | Apache Airflow 3.0.2 | Workflow automation & scheduling |
| **Experiment Tracking** | MLflow + PostgreSQL | Model versioning & metrics |
| **Storage** | AWS S3 | Model artifacts & datasets |
| **Containerization** | Docker + Docker Compose | Service deployment |
| **Load Balancing** | Nginx | Traffic splitting (80/20) |
| **API Framework** | Flask | Inference endpoints |
| **Monitoring** | Prometheus + Grafana | Performance & system metrics |
| **Testing** | pytest + Locust | Unit, integration & load testing |
| **CI/CD** | GitHub Actions | Automated testing & deployment |
| **Infrastructure** | Pulumi (AWS) | Infrastructure as Code |

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- AWS credentials configured (for S3 access)
- Python 3.10+ (for local development)

### 1. Environment Setup
```bash
# Clone repository
git clone <repository-url>
cd airflow

# Configure environment
cp .env.example .env
# Edit .env with your AWS credentials and S3 bucket name
```

### 2. Deploy Core Stack
```bash
# Start Airflow, MLflow, PostgreSQL
docker compose up -d

# Verify services are running
docker compose ps
```

### 3. Deploy A/B Testing Infrastructure
```bash
# Set S3 bucket environment variable
export MLFLOW_S3_BUCKET=your-mlops-bucket

# Start inference services with A/B testing
docker compose -f docker-compose.yaml -f docker-compose.ab.yml up -d --build
```

### 4. Deploy Monitoring Stack
```bash
# Start Prometheus + Grafana
docker compose -f monitoring/docker-compose.monitoring.yml up -d
```

### 5. Access Services
| Service | URL | Credentials |
|---------|-----|-------------|
| **Frontend** | http://localhost:6500 | - |
| **Airflow UI** | http://localhost:8080 | airflow/airflow |
| **MLflow UI** | http://localhost:5000 | - |
| **Grafana** | http://localhost:3000 | admin/admin |
| **Prometheus** | http://localhost:9090 | - |
| **API (Load Balanced)** | http://localhost:7000 | - |

### 6. Run Tests
```bash
# Install test dependencies
pip install -r tests/requirements-test.txt

# Run all tests
python tests/run_tests.py

# Run specific test types
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v
```

## 🔄 A/B Testing Workflow

### Model Versioning System
- **Best Models (Production)**: `price_check_BO1/`, `price_check_BO2/`, `price_check_BO3/`...
- **Candidate Models**: `price_check_CO1/`, `price_check_CO2/`, `price_check_CO3/`...
- **Datasets**: `train_V1.csv`, `train_V2.csv`, `train_V3.csv`...

### Automated A/B Testing Process

1. **Candidate Generation**
   - Main training DAG detects need for new candidate
   - Trains model on latest dataset with hyperparameter tuning
   - Saves artifacts to S3 as `price_check_CO{n+1}`
   - Restarts candidate container and triggers evaluation

2. **Traffic Splitting**
   - Nginx router splits traffic: **80% production**, **20% candidate**
   - Hash-based routing ensures user consistency
   - All requests logged with variant identifier

3. **Performance Monitoring**
   - Real-time metrics: latency, accuracy, user feedback
   - User feedback collection: star ratings, accuracy assessments
   - Drift detection: statistical analysis of feature distributions

4. **Automated Decision Making**
   - **Hourly evaluation** via `evaluate_ab_dag`
   - **Safety checks**: minimum traffic (≥50 requests), feedback (≥10 ratings)
   - **Composite scoring**: weighted accuracy + latency performance
   - **Decision thresholds**: promote if >5% better, rollback if >20% worse

5. **Model Promotion/Rollback**
   - **Promotion**: Copy `CO{n}` → `BO{n+1}`, restart production container
   - **Rollback**: Delete candidate artifacts, trigger retraining
   - **Audit logging**: All decisions recorded with performance metrics

### Example Decision Logic
```python
# Composite scoring
accuracy_score = user_rating / 5.0
latency_score = max(0, (5000 - avg_latency_ms) / 5000)
composite_score = accuracy_score * 0.7 + latency_score * 0.3

# Decision rules
if candidate_score > production_score * 1.05:  # 5% better
    return "promote"
elif candidate_score < production_score * 0.8:  # 20% worse
    return "rollback"
else:
    return "continue_testing"
```

## 📁 Project Structure

```
airflow/
├── dags/                           # Airflow DAGs
│   ├── bangalore_home_prices_dag.py    # Main training pipeline
│   ├── evaluate_ab_dag.py              # A/B testing evaluation
│   ├── drift_monitoring_dag.py         # Data drift detection
│   ├── mlflow_utils.py                 # MLflow integration
│   ├── s3_utils.py                     # S3 operations
│   ├── train_model.py                  # Model training logic
│   ├── validate_model.py               # Model validation
│   └── version_utils.py                # Model versioning
├── inference/
│   ├── backend/                        # Flask API services
│   │   ├── inference_api.py               # Main API endpoints
│   │   ├── drift_monitor_simple.py        # Drift detection
│   │   ├── log_db.py                      # Database logging
│   │   └── util.py                        # Utility functions
│   └── frontend/                       # Static web interface
│       ├── index.html                     # User interface
│       ├── main.js                        # Frontend logic
│       └── nginx.conf                     # Nginx configuration
├── tests/                          # Comprehensive test suite
│   ├── unit/                           # Unit tests (4/4 passing)
│   ├── integration/                    # API tests (7/7 passing)
│   ├── load/                           # Load testing (Locust)
│   └── conftest.py                     # Test fixtures
├── monitoring/                     # Observability stack
│   ├── grafana/                        # Grafana dashboards
│   ├── prometheus.yml                  # Prometheus configuration
│   └── docker-compose.monitoring.yml   # Monitoring services
├── iac/                           # Infrastructure as Code
│   ├── components/                     # Pulumi components
│   └── __main__.py                     # Infrastructure definition
├── documentations/                # Comprehensive documentation
│   ├── abtest.md                      # A/B testing implementation
│   ├── automated-testing.md           # Testing strategy
│   ├── evidently.md                   # Drift monitoring
│   ├── inference.md                   # API documentation
│   ├── monitoring.md                  # Observability setup
│   └── milestone.md                   # Project progress
├── router/nginx.conf              # Traffic splitting configuration
├── docker-compose.yaml            # Core services
├── docker-compose.ab.yml          # A/B testing services
└── .github/workflows/deploy.yml   # CI/CD pipeline
```

## 🔌 API Endpoints

### Inference API
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/predict_home_price` | POST | Main prediction endpoint |
| `/api/get_location_names` | GET | Available locations |
| `/api/health` | GET | System health & metrics |
| `/api/metrics` | GET | Performance metrics (JSON) |
| `/metrics` | GET | Prometheus format metrics |
| `/api/feedback` | POST | User feedback collection |
| `/api/logs` | GET | Request/feedback logs |
| `/api/drift_report` | GET | Data drift analysis |

### Example Usage
```bash
# Make prediction
curl -X POST http://localhost:7000/api/predict_home_price \
  -H "Content-Type: application/json" \
  -d '{"total_sqft": 1000, "location": "Whitefield", "bhk": 2, "bath": 2}'

# Get system metrics
curl http://localhost:6001/api/metrics

# Submit feedback
curl -X POST http://localhost:7000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{"prediction_id": 29, "feedback_type": "rating", "feedback_value": 5}'
```

## 📊 Monitoring & Observability

### Key Metrics Tracked
- **Request Rates**: Predictions per second by variant
- **Latency Distribution**: P95, P99 response times
- **Error Rates**: Failed predictions and system errors
- **User Feedback**: Ratings, accuracy assessments
- **System Resources**: CPU, memory, disk usage
- **Data Drift**: Feature distribution changes

### Dashboards Available
- **Grafana**: Performance metrics and system health
- **MLflow**: Experiment tracking and model comparison
- **Airflow**: Pipeline monitoring and task status
- **Prometheus**: Raw metrics and alerting

## 🧪 Testing Strategy

### Test Coverage (100% Pass Rate)
- **Unit Tests**: 4/4 passing - Core functionality validation
- **Integration Tests**: 7/7 passing - API endpoint verification
- **Load Tests**: Locust framework for performance validation
- **CI/CD Integration**: Automated testing in GitHub Actions

### Running Tests
```bash
# All tests
python tests/run_tests.py

# Specific test types
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v

# Load testing
cd tests/load && locust -f locustfile.py --host=http://localhost:6001
```

## 🚨 Data Drift Detection

### Evidently-Inspired Implementation
- **Statistical Analysis**: Mean comparison with configurable thresholds
- **Multi-Feature Monitoring**: sqft, bhk, bath, prediction distributions
- **Automated Alerts**: Integration with A/B evaluation pipeline
- **API Access**: Real-time drift reports via `/api/drift_report`

### Drift Response
```json
{
  "overall_drift_detected": true,
  "drift_indicators": {
    "prediction": {
      "drift_percentage": 42.6,
      "significant_drift": true
    }
  }
}
```

## 🔧 Configuration

### Environment Variables
```bash
# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
MLFLOW_S3_BUCKET=your-mlops-bucket

# Database Configuration
POSTGRES_USER=airflow
POSTGRES_PASSWORD=airflow
POSTGRES_DB=airflow

# Model Configuration
MODEL_PREFIX=best_model  # or candidate_model
```

### Airflow Configuration
- **Scheduler**: Runs training pipeline weekly
- **Evaluation**: Hourly A/B testing assessment
- **Drift Monitoring**: Daily data distribution analysis
- **Web UI**: Available at http://localhost:8080

## 🏆 Project Achievements

### Requirements Completion (90% Core Features)
✅ **Environment Setup**: Docker, Airflow, MLflow, S3 integration  
✅ **Automated Training**: Scheduled DAGs with experiment tracking  
✅ **A/B Testing**: Traffic splitting with performance comparison  
✅ **Automated Rollbacks**: Threshold-based promotion/rollback logic  
✅ **Inference API**: 8 endpoints with comprehensive functionality  
✅ **Model Versioning**: Custom BO/CO versioning system  
✅ **Testing**: 100% test pass rate with CI/CD integration  
✅ **Monitoring**: Prometheus + Grafana observability stack  
✅ **Documentation**: Comprehensive guides and API docs  

### Production-Ready Features
- **Zero-downtime deployments** with automated container restarts
- **Comprehensive logging** for audit trails and debugging
- **Safety checks** preventing bad model deployments
- **User feedback integration** for continuous improvement
- **Data drift detection** with automated alerts
- **Load testing** framework for scalability validation

## 🔮 Future Enhancements

### Short Term
- [ ] **Slack/Email notifications** for promotion/rollback events
- [ ] **Advanced Grafana dashboards** with business metrics
- [ ] **Batch prediction support** for bulk processing
- [ ] **API authentication** and security hardening

### Long Term
- [ ] **Kubernetes deployment** with auto-scaling capabilities
- [ ] **Multi-model ensembles** as candidate approaches
- [ ] **Feature stores** for advanced data management
- [ ] **Geographical A/B testing** for regional optimization

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`python tests/run_tests.py`)
4. Commit changes (`git commit -m 'Add amazing feature'`)
5. Push to branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Apache Airflow** for workflow orchestration
- **MLflow** for experiment tracking
- **Evidently AI** for drift detection inspiration
- **Prometheus & Grafana** for monitoring capabilities

---

**Built with ❤️ for production-ready MLOps**
