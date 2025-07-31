# Monitoring Strategy

## Overview
Real-time monitoring of A/B testing infrastructure using Prometheus + Grafana to track model performance, system health, and user feedback.

## Architecture
```
Inference Services → Prometheus → Grafana
    (metrics)      (collection)  (visualization)
```

## Metrics Collected

### Performance Metrics
- `predictions_total` - Request count by variant
- `prediction_duration_seconds` - Response time histogram
- `prediction_errors_total` - Error rates by type

### System Metrics  
- `system_cpu_percent` - CPU usage by variant
- `system_memory_percent` - Memory usage by variant

### Business Metrics
- `feedback_total` - User feedback by type (rating, accurate, etc.)

## Setup

### Deploy Monitoring Stack
```bash
docker compose -f monitoring/docker-compose.monitoring.yml up -d
```

### Access Points
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
- **Metrics Endpoints**: 
  - Production: http://localhost:6001/metrics
  - Candidate: http://localhost:6002/metrics

## Key Dashboards

### A/B Testing Performance
- Prediction rates comparison (prod vs candidate)
- 95th percentile response times
- Error rates by variant
- System resource utilization