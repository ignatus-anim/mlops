import pytest
import sys
import os
from unittest.mock import Mock

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

@pytest.fixture
def sample_prediction_data():
    return {
        'total_sqft': 1000,
        'location': '1st Block Jayanagar',
        'bhk': 2,
        'bath': 2
    }

@pytest.fixture
def mock_s3_client():
    mock_client = Mock()
    mock_client.download_file.return_value = None
    mock_client.upload_file.return_value = None
    return mock_client

@pytest.fixture
def sample_model_artifacts():
    return {
        'model_file': 'banglore_home_prices_model.pickle',
        'columns_file': 'columns.json'
    }