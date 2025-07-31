"""
Simple statistical drift monitoring without Evidently dependencies
"""
import pandas as pd
import json
import numpy as np
from datetime import datetime, timedelta
from log_db import get_conn, ENGINE_STR
from sqlalchemy import create_engine, text
import logging

def convert_numpy_types(obj):
    """Convert numpy types to native Python types"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    return obj

def get_reference_data():
    """Get reference dataset for drift comparison"""
    engine = create_engine(ENGINE_STR)
    
    # Use older data as reference (fallback to synthetic if none exists)
    query = """
    SELECT 
        (features->>'total_sqft')::float as total_sqft,
        (features->>'bhk')::int as bhk,
        (features->>'bath')::int as bath,
        features->>'location' as location,
        (features->>'prediction')::float as prediction
    FROM feature_logs 
    WHERE ts < NOW() - INTERVAL '7 days'
    ORDER BY ts DESC 
    LIMIT 100
    """
    
    try:
        df = pd.read_sql(query, engine)
        if df.empty:
            # Create synthetic reference data
            df = pd.DataFrame({
                'total_sqft': [1000, 1500, 2000, 1200, 1800],
                'bhk': [2, 3, 4, 2, 3],
                'bath': [2, 2, 3, 2, 3],
                'location': ['1st Block Jayanagar', 'Whitefield', 'Electronic City', 'Koramangala', 'Indiranagar'],
                'prediction': [45.0, 65.0, 85.0, 50.0, 70.0]
            })
        return df
    except Exception as e:
        logging.error(f"Error getting reference data: {e}")
        # Return synthetic data as fallback
        return pd.DataFrame({
            'total_sqft': [1000, 1500, 2000, 1200, 1800],
            'bhk': [2, 3, 4, 2, 3],
            'bath': [2, 2, 3, 2, 3],
            'location': ['1st Block Jayanagar', 'Whitefield', 'Electronic City', 'Koramangala', 'Indiranagar'],
            'prediction': [45.0, 65.0, 85.0, 50.0, 70.0]
        })

def get_current_data(days_back=7):
    """Get recent prediction data for drift comparison"""
    engine = create_engine(ENGINE_STR)
    
    query = """
    SELECT 
        (features->>'total_sqft')::float as total_sqft,
        (features->>'bhk')::int as bhk,
        (features->>'bath')::int as bath,
        features->>'location' as location,
        (features->>'prediction')::float as prediction
    FROM feature_logs 
    WHERE ts > NOW() - INTERVAL '%s days'
    ORDER BY ts DESC
    """ % days_back
    
    try:
        df = pd.read_sql(query, engine)
        return df
    except Exception as e:
        logging.error(f"Error getting current data: {e}")
        return pd.DataFrame()

def get_drift_summary():
    """Get simplified drift summary for API endpoint"""
    try:
        reference_data = get_reference_data()
        current_data = get_current_data(days_back=7)
        
        if current_data.empty:
            return {"status": "no_current_data", "message": "No recent data available"}
        
        # Generate basic statistics comparison
        ref_stats = reference_data.describe()
        curr_stats = current_data.describe()
        
        # Simple drift indicators
        drift_indicators = {}
        for col in ['total_sqft', 'bhk', 'bath', 'prediction']:
            if col in ref_stats.columns and col in curr_stats.columns:
                ref_mean = ref_stats.loc['mean', col]
                curr_mean = curr_stats.loc['mean', col]
                drift_pct = abs(curr_mean - ref_mean) / ref_mean * 100 if ref_mean != 0 else 0
                
                # Convert all values to native Python types
                drift_indicators[col] = {
                    'reference_mean': float(ref_mean.item() if hasattr(ref_mean, 'item') else ref_mean),
                    'current_mean': float(curr_mean.item() if hasattr(curr_mean, 'item') else curr_mean),
                    'drift_percentage': float(drift_pct.item() if hasattr(drift_pct, 'item') else drift_pct),
                    'significant_drift': bool((drift_pct > 20).item() if hasattr(drift_pct > 20, 'item') else drift_pct > 20)
                }
        
        result = {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "data_points": {
                "reference": len(reference_data),
                "current": len(current_data)
            },
            "drift_indicators": drift_indicators,
            "overall_drift_detected": any(
                indicator.get('significant_drift', False) 
                for indicator in drift_indicators.values()
            )
        }
        
        return convert_numpy_types(result)
        
    except Exception as e:
        logging.error(f"Error getting drift summary: {e}")
        return {"status": "error", "message": str(e)}