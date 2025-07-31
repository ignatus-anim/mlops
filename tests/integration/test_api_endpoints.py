import pytest
import requests
import json
from unittest.mock import patch

class TestAPIEndpoints:
    
    BASE_URL = "http://localhost:6001"
    
    def test_health_endpoint(self):
        """Test health check endpoint"""
        try:
            response = requests.get(f"{self.BASE_URL}/api/health", timeout=5)
            assert response.status_code == 200
            
            data = response.json()
            assert data['status'] == 'healthy'
            assert 'timestamp' in data
            assert 'system' in data
            assert 'model_variant' in data
        except requests.exceptions.ConnectionError:
            pytest.skip("Inference service not running")
    
    def test_get_location_names(self):
        """Test location names endpoint"""
        try:
            response = requests.get(f"{self.BASE_URL}/api/get_location_names", timeout=5)
            assert response.status_code == 200
            
            data = response.json()
            assert 'locations' in data
            assert isinstance(data['locations'], list)
            assert len(data['locations']) > 0
        except requests.exceptions.ConnectionError:
            pytest.skip("Inference service not running")
    
    def test_predict_home_price_valid(self, sample_prediction_data):
        """Test prediction endpoint with valid data"""
        try:
            response = requests.post(
                f"{self.BASE_URL}/api/predict_home_price",
                data=sample_prediction_data,
                timeout=5
            )
            assert response.status_code == 200
            
            data = response.json()
            assert 'estimated_price' in data
            assert 'prediction_id' in data
            assert 'response_time_ms' in data
            assert isinstance(data['estimated_price'], (int, float))
            assert data['estimated_price'] > 0
        except requests.exceptions.ConnectionError:
            pytest.skip("Inference service not running")
    
    def test_predict_home_price_missing_params(self):
        """Test prediction endpoint with missing parameters"""
        try:
            response = requests.post(
                f"{self.BASE_URL}/api/predict_home_price",
                data={'total_sqft': 1000},  # Missing other required params
                timeout=5
            )
            assert response.status_code == 500  # Should handle gracefully
        except requests.exceptions.ConnectionError:
            pytest.skip("Inference service not running")
    
    def test_metrics_endpoint(self):
        """Test metrics endpoint"""
        try:
            response = requests.get(f"{self.BASE_URL}/api/metrics", timeout=5)
            assert response.status_code == 200
            
            data = response.json()
            assert 'variant' in data
            assert 'predictions' in data
            assert 'feedback' in data
            assert 'timestamp' in data
        except requests.exceptions.ConnectionError:
            pytest.skip("Inference service not running")
    
    def test_prometheus_metrics_endpoint(self):
        """Test Prometheus metrics endpoint"""
        try:
            response = requests.get(f"{self.BASE_URL}/metrics", timeout=5)
            assert response.status_code == 200
            assert 'predictions_total' in response.text
            assert 'prediction_duration_seconds' in response.text
        except requests.exceptions.ConnectionError:
            pytest.skip("Inference service not running")
    
    def test_feedback_endpoint(self):
        """Test feedback submission endpoint"""
        try:
            feedback_data = {
                'prediction_id': 1,
                'feedback_type': 'rating',
                'feedback_value': 5,
                'feedback_text': 'Test feedback'
            }
            
            response = requests.post(
                f"{self.BASE_URL}/api/feedback",
                json=feedback_data,
                timeout=5
            )
            # Should return 200 or 400 (if prediction_id doesn't exist)
            assert response.status_code in [200, 400]
        except requests.exceptions.ConnectionError:
            pytest.skip("Inference service not running")