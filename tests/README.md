# Testing Suite for ML Pipeline

This directory contains comprehensive tests for the Bangalore Home Price Prediction MLOps pipeline.

## Test Structure

```
tests/
├── unit/                    # Unit tests for individual functions
│   ├── test_basic_functions.py    # Basic functionality tests
│   ├── test_inference_logic.py    # Inference utility tests  
│   └── test_version_utils.py      # Version management tests
├── integration/             # Integration tests for APIs
│   └── test_api_endpoints.py      # Flask API endpoint tests
├── load/                    # Load testing scenarios
│   └── locustfile.py             # Locust load test definitions
├── conftest.py             # Pytest fixtures and configuration
├── requirements-test.txt   # Testing dependencies
├── run_tests.py           # Test runner script
└── README.md              # This file
```

## Running Tests

### Quick Start
```bash
# Install test dependencies
pip install -r tests/requirements-test.txt

# Run all tests
python3 tests/run_tests.py

# Or run specific test types
python3 -m pytest tests/unit/ -v
python3 -m pytest tests/integration/ -v
```

### Individual Test Categories

**Unit Tests** - Test individual functions and utilities:
```bash
python3 -m pytest tests/unit/test_basic_functions.py -v
python3 -m pytest tests/unit/test_version_utils.py -v
```

**Integration Tests** - Test API endpoints (requires running services):
```bash
python3 -m pytest tests/integration/test_api_endpoints.py -v
```

**Load Tests** - Performance testing with Locust:
```bash
cd tests/load
locust -f locustfile.py --host=http://localhost:6001
```

## Test Coverage

### ✅ **Working Tests**

**Unit Tests:**
- ✅ Version number extraction from S3 keys
- ✅ Model version management (BO/CO versioning)
- ✅ Dataset version tracking
- ✅ Basic function imports and structure

**Integration Tests:**
- ✅ Health check endpoint (`/api/health`)
- ✅ Location names endpoint (`/api/get_location_names`)
- ✅ Prediction endpoint (`/api/predict_home_price`)
- ✅ Metrics endpoint (`/api/metrics`)
- ✅ Prometheus metrics endpoint (`/metrics`)
- ✅ Feedback endpoint (`/api/feedback`)

**Load Tests:**
- ✅ Concurrent prediction requests
- ✅ Health check load testing
- ✅ Metrics endpoint performance
- ✅ Mixed workload scenarios

### ⚠️ **Partially Working Tests**

**Unit Tests:**
- ⚠️ Inference logic tests (require complex S3 mocking)
- ⚠️ Model loading tests (depend on actual S3 artifacts)

## Test Results Summary

```
Unit Tests:        8/11 passing (73%)
Integration Tests: 7/7 passing (100%)
Load Tests:        Available via Locust
Overall:          15/18 passing (83%)
```

## Key Testing Scenarios

### Unit Test Examples
- **Version Management**: Extract version numbers from S3 keys
- **Function Validation**: Ensure all required functions exist
- **Data Fixtures**: Validate test data structure

### Integration Test Examples
- **API Functionality**: All endpoints return expected responses
- **Error Handling**: Invalid requests handled gracefully
- **Data Format**: Response JSON matches expected schema

### Load Test Examples
- **Prediction Load**: 100+ concurrent prediction requests
- **Mixed Workload**: 70% predictions, 20% health checks, 10% metrics
- **Performance Baseline**: Response times under 100ms

## Dependencies

```
pytest==7.4.0          # Testing framework
pytest-mock==3.11.1    # Mocking utilities
requests==2.31.0       # HTTP client for integration tests
locust==2.15.1         # Load testing (install separately)
```

## Usage Examples

### Running Specific Tests
```bash
# Test only version utilities
python3 -m pytest tests/unit/test_version_utils.py::TestVersionUtils::test_get_latest_dataset_version -v

# Test API health endpoint
python3 -m pytest tests/integration/test_api_endpoints.py::TestAPIEndpoints::test_health_endpoint -v

# Run tests with coverage
python3 -m pytest tests/ --cov=inference --cov=dags
```

### Load Testing
```bash
# Start load test with 10 users
locust -f tests/load/locustfile.py --host=http://localhost:6001 -u 10 -r 2

# Headless load test for 60 seconds
locust -f tests/load/locustfile.py --host=http://localhost:6001 -u 50 -r 5 -t 60s --headless
```

## Test Environment Requirements

### For Unit Tests
- Python 3.10+
- pytest and dependencies
- No external services required

### For Integration Tests
- Running inference services (`docker compose up -d`)
- Accessible endpoints on localhost:6001/6002
- Database connectivity

### For Load Tests
- Locust installed (`pip install locust`)
- Target services running and accessible
- Sufficient system resources for load generation

## Continuous Integration

The test suite is designed to work in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Tests
  run: |
    pip install -r tests/requirements-test.txt
    python3 -m pytest tests/unit/ -v
    python3 -m pytest tests/integration/ -v --tb=short
```

## Future Enhancements

- [ ] Add database integration tests
- [ ] Implement test data factories
- [ ] Add performance regression testing
- [ ] Create mock S3 service for unit tests
- [ ] Add contract testing between services
- [ ] Implement chaos engineering tests