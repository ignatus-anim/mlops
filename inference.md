# Inference API Documentation

This document describes all API endpoints available in the inference backend services (`infer-prod` and `infer-cand`).

## Base URLs
- **Production**: http://localhost:6001
- **Candidate**: http://localhost:6002
- **Router (Load Balanced)**: http://localhost:7000

## API Endpoints

### 1. Prediction Endpoints

#### `GET/POST /api/predict_home_price`
**Purpose**: Main prediction endpoint for home price estimation

**Request Parameters**:
```json
{
  "total_sqft": 1000,
  "location": "1st Block Jayanagar", 
  "bhk": 2,
  "bath": 2
}
```

**Response**:
```json
{
  "estimated_price": 42.01,
  "prediction_id": 29,
  "response_time_ms": 0.38
}
```

**Features**:
- Generates unique session ID for tracking
- Logs request to database with timing
- Updates Prometheus metrics
- Handles prediction errors gracefully

#### `GET /api/get_location_names`
**Purpose**: Returns available location options for predictions

**Response**:
```json
{
  "locations": ["1st Block Jayanagar", "Whitefield", "Electronic City", ...]
}
```

### 2. Feedback Endpoints

#### `POST /api/feedback`
**Purpose**: Collect user feedback on prediction accuracy

**Request**:
```json
{
  "prediction_id": 29,
  "feedback_type": "rating|accurate|too_high|too_low|actual_price",
  "feedback_value": 5,
  "feedback_text": "Very accurate prediction"
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Feedback recorded"
}
```

**Features**:
- Links feedback to specific predictions
- Supports multiple feedback types
- Updates Prometheus feedback counters
- Uses session-based prediction tracking

### 3. Monitoring Endpoints

#### `GET /api/metrics`
**Purpose**: JSON-formatted performance metrics for dashboards

**Response**:
```json
{
  "variant": "best_model",
  "time_period_hours": 24,
  "timestamp": "2025-07-31T13:58:16.931606",
  "predictions": {
    "total_count": 13,
    "avg_latency_ms": 0.23,
    "p95_latency_ms": 0.44,
    "p99_latency_ms": 0.47,
    "min_latency_ms": 0.16,
    "max_latency_ms": 0.48
  },
  "feedback": {
    "total_count": 7,
    "avg_rating": 5.0,
    "accurate_count": 5,
    "too_high_count": 0,
    "too_low_count": 0
  }
}
```

**Query Parameters**:
- `hours` (default: 24) - Time window for metrics

#### `GET /metrics`
**Purpose**: Prometheus-formatted metrics for monitoring

**Response**: Prometheus exposition format
```
# HELP predictions_total Total predictions
# TYPE predictions_total counter
predictions_total{endpoint="predict",variant="best_model"} 13.0

# HELP prediction_duration_seconds Prediction latency
# TYPE prediction_duration_seconds histogram
prediction_duration_seconds_bucket{le="0.005",variant="best_model"} 13.0
...
```

**Metrics Exposed**:
- `predictions_total` - Request counters
- `prediction_duration_seconds` - Latency histograms
- `prediction_errors_total` - Error counters
- `system_cpu_percent` - CPU usage
- `system_memory_percent` - Memory usage
- `feedback_total` - Feedback counters

#### `GET /api/health`
**Purpose**: Health check with system metrics

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-07-31T14:04:57.781302",
  "model_variant": "candidate_model",
  "system": {
    "cpu_percent": 7.4,
    "memory_percent": 68.4,
    "memory_available_gb": 9.85,
    "disk_percent": 44.4,
    "disk_free_gb": 247.06
  },
  "database": "healthy"
}
```

**Features**:
- Tests database connectivity
- Updates Prometheus system metrics
- Real-time resource monitoring

### 4. Logging Endpoints

#### `GET /api/logs`
**Purpose**: Retrieve recent prediction or feedback logs

**Query Parameters**:
- `type` - "predictions" or "feedback" (default: predictions)
- `limit` - Number of records (default: 100)

**Response**:
```json
{
  "logs": [
    {
      "prediction_id": 29,
      "variant": "best_model",
      "location": "1st Block Jayanagar",
      "sqft": 1000,
      "bhk": 2,
      "bath": 2,
      "prediction": 42.01,
      "prediction_time_ms": 0.38,
      "session_id": "15b510eb-13c4-4f2e-bf28-b2e38c8b69e5",
      "user_ip": "172.18.0.1",
      "ts": "2025-07-31 13:49:06.155423"
    }
  ],
  "count": 1,
  "log_type": "predictions",
  "timestamp": "2025-07-31T14:04:21.001832"
}
```

#### `GET /api/logs/tail`
**Purpose**: Live log streaming (last N entries)

**Query Parameters**:
- `type` - Log type (predictions/feedback)
- `lines` - Number of lines (default: 10)

**Response**: Same format as `/api/logs`

## Model Variants

Each inference service loads models based on the `MODEL_PREFIX` environment variable:

- **Production (`infer-prod`)**: `MODEL_PREFIX=best_model`
  - Loads from S3: `s3://mlops-bucket/best_model/`
  - Serves 80% of traffic via router

- **Candidate (`infer-cand`)**: `MODEL_PREFIX=candidate_model`  
  - Loads from S3: `s3://mlops-bucket/candidate_model/`
  - Serves 20% of traffic via router

## Session Management

- **Session IDs**: Generated per user session for tracking
- **Prediction Linking**: Last prediction ID stored in session for feedback
- **IP Tracking**: User IP logged for analytics
- **Cross-Request State**: Feedback can reference previous predictions

## Error Handling

All endpoints include comprehensive error handling:

- **400 Bad Request**: Missing required parameters
- **404 Not Found**: Invalid endpoints or missing resources
- **500 Internal Server Error**: Database/model errors

Error responses include descriptive messages and are logged for debugging.

## Performance Characteristics

- **Prediction Latency**: Sub-millisecond response times
- **Throughput**: Handles concurrent requests efficiently
- **Resource Usage**: Monitored via health endpoint
- **Database Logging**: Asynchronous to avoid blocking requests

## Integration Points

- **Database**: PostgreSQL for request/feedback logging
- **S3**: Model artifact storage and loading
- **Prometheus**: Metrics collection and monitoring
- **Nginx**: Load balancing and traffic splitting
- **Frontend**: JavaScript client for user interactions