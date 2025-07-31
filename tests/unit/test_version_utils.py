import pytest
from unittest.mock import patch, Mock
import sys
import os

# Add dags to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../dags'))

class TestVersionUtils:
    
    @patch('version_utils.get_s3_client')
    def test_get_latest_dataset_version(self, mock_get_s3):
        """Test getting latest dataset version"""
        mock_s3 = Mock()
        mock_get_s3.return_value = mock_s3
        mock_s3.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'data/raw/train_V1.csv'},
                {'Key': 'data/raw/train_V3.csv'},
                {'Key': 'data/raw/train_V2.csv'}
            ]
        }
        
        from version_utils import get_latest_dataset_version
        
        version, key = get_latest_dataset_version()
        assert version == 3
        assert 'train_V3.csv' in key
    
    @patch('version_utils.get_s3_client')
    def test_get_latest_model_version_bo(self, mock_get_s3):
        """Test getting latest BO model version"""
        mock_s3 = Mock()
        mock_get_s3.return_value = mock_s3
        mock_s3.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'models/price_check_BO1/model.pickle'},
                {'Key': 'models/price_check_BO3/model.pickle'},
                {'Key': 'models/price_check_BO2/model.pickle'}
            ]
        }
        
        from version_utils import get_latest_model_version
        
        version, prefix = get_latest_model_version('BO')
        assert version == 3
        assert 'price_check_BO3' in prefix
    
    @patch('version_utils.get_s3_client')
    def test_get_next_model_version(self, mock_get_s3):
        """Test getting next model version"""
        mock_s3 = Mock()
        mock_get_s3.return_value = mock_s3
        mock_s3.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'models/price_check_CO1/model.pickle'},
                {'Key': 'models/price_check_CO2/model.pickle'}
            ]
        }
        
        from version_utils import get_next_model_version
        
        version, prefix = get_next_model_version('CO')
        assert version == 3
        assert 'price_check_CO3' in prefix
    
    @patch('version_utils.get_s3_client')
    def test_get_next_model_version_no_existing(self, mock_get_s3):
        """Test getting next version when no models exist"""
        mock_s3 = Mock()
        mock_get_s3.return_value = mock_s3
        mock_s3.list_objects_v2.return_value = {'Contents': []}
        
        from version_utils import get_next_model_version
        
        version, prefix = get_next_model_version('BO')
        assert version == 2  # Next after default 1
        assert 'price_check_BO2' in prefix