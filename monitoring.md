# Monitoring Strategy

## Overview
Real-time monitoring of A/B testing infrastructure using Prometheus + Grafana to track model performance, system health, and user feedback.

## Architecture
```
Inference Services → Prometheus → Grafana
    (metrics)      (collection)  (visualization)
```

## Metrics Collected

### Application Metrics
- `predictions_total{endpoint="predict",variant="best_model|candidate_model"}` - Counter of total predictions
- `prediction_duration_seconds{variant="best_model|candidate_model"}` - Histogram of prediction latency (buckets: 0.005s to 10s)
- `prediction_errors_total{variant="...",error_type="..."}` - Counter of prediction errors by type
- `system_cpu_percent{variant="..."}` - Gauge for CPU usage (updated via /api/health)
- `system_memory_percent{variant="..."}` - Gauge for memory usage (updated via /api/health)
- `feedback_total{variant="...",feedback_type="rating|accurate|too_high|too_low"}` - Counter of user feedback

### Default Python/Process Metrics
- `python_gc_*` - Python garbage collection statistics
- `python_info` - Python version information
- `process_virtual_memory_bytes` - Virtual memory usage
- `process_resident_memory_bytes` - Resident memory usage
- `process_cpu_seconds_total` - Total CPU time
- `process_open_fds` - Open file descriptors

## Setup

### Deploy Monitoring Stack
```bash
docker compose -f monitoring/docker-compose.monitoring.yml up -d
```

### Access Points
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
- **Metrics Endpoints**: 
  - Production: http://localhost:6001/metrics (Prometheus format)
  - Candidate: http://localhost:6002/metrics (Prometheus format)
  - JSON Metrics: http://localhost:6001/api/metrics, http://localhost:6002/api/metrics
  - Health Check: http://localhost:6001/api/health (updates system metrics)

## Prometheus Queries

### Performance Analysis
```promql
# Request rate per second
rate(predictions_total[5m])

# 95th percentile latency
histogram_quantile(0.95, prediction_duration_seconds)

# Average response time
prediction_duration_seconds_sum / prediction_duration_seconds_count

# Error rate
rate(prediction_errors_total[5m])
```

### A/B Testing Comparison
```promql
# Request rate by variant
sum(rate(predictions_total[5m])) by (variant)

# Latency comparison
histogram_quantile(0.95, sum(prediction_duration_seconds) by (variant, le))

# System resource usage
system_cpu_percent
system_memory_percent
```

## Key Dashboards

### A/B Testing Performance
- Prediction rates comparison (prod vs candidate)
- 95th percentile response times
- Error rates by variant
- System resource utilization