import pytest
import sys
import os
from unittest.mock import Mock

# Add project paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../inference/backend'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../dags'))

class TestBasicFunctions:
    
    def test_version_utils_extract_version_number(self):
        """Test version number extraction"""
        from version_utils import extract_version_number
        
        # Test dataset version extraction
        result = extract_version_number('data/raw/train_V5.csv', r'train_V(\d+)\.csv')
        assert result == 5
        
        # Test model version extraction
        result = extract_version_number('models/price_check_BO3/model.pickle', r'price_check_BO(\d+)/')
        assert result == 3
        
        # Test no match
        result = extract_version_number('invalid_key', r'train_V(\d+)\.csv')
        assert result is None
    
    def test_version_utils_bucket_constant(self):
        """Test bucket constant is defined"""
        from version_utils import BUCKET
        assert BUCKET == "mlops-bucket0982"
    
    def test_inference_util_imports(self):
        """Test that util module imports correctly"""
        import util
        
        # Test that functions exist
        assert hasattr(util, 'get_estimated_price')
        assert hasattr(util, 'get_location_names')
        assert hasattr(util, 'load_saved_artifacts')
        assert callable(util.get_estimated_price)
        assert callable(util.get_location_names)
        assert callable(util.load_saved_artifacts)
    
    def test_sample_data_fixture(self, sample_prediction_data):
        """Test that fixtures work correctly"""
        assert 'total_sqft' in sample_prediction_data
        assert 'location' in sample_prediction_data
        assert 'bhk' in sample_prediction_data
        assert 'bath' in sample_prediction_data
        assert sample_prediction_data['total_sqft'] == 1000
        assert sample_prediction_data['bhk'] == 2