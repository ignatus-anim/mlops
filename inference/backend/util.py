import pickle
import json
import numpy as np
import boto3
import os
import re
import logging
from io import BytesIO

__locations = None
__data_columns = None
__model = None

def get_estimated_price(location,sqft,bhk,bath):
    try:
        loc_index = __data_columns.index(location.lower())
    except:
        loc_index = -1

    x = np.zeros(len(__data_columns))
    x[0] = sqft
    x[1] = bath
    x[2] = bhk
    if loc_index>=0:
        x[loc_index] = 1

    return round(__model.predict([x])[0],2)


def get_latest_model_version(model_type='BO'):
    """Get the latest model version from S3"""
    bucket_name = os.environ.get('MLFLOW_S3_BUCKET', 'mlops-bucket0982')
    s3 = boto3.client('s3')
    
    # Override model type based on MODEL_PREFIX env var
    model_prefix = os.environ.get('MODEL_PREFIX', '')
    if 'candidate' in model_prefix.lower():
        model_type = 'CO'
    elif 'best' in model_prefix.lower():
        model_type = 'BO'
    
    try:
        # List all objects with the model prefix
        prefix = f"models/price_check_{model_type}"
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        
        if 'Contents' not in response:
            logging.warning(f"No {model_type} models found, falling back to legacy path")
            return get_legacy_model_path()
        
        # Extract version numbers
        versions = []
        for obj in response['Contents']:
            match = re.search(rf'price_check_{model_type}(\d+)/', obj['Key'])
            if match:
                versions.append(int(match.group(1)))
        
        if not versions:
            logging.warning(f"No versioned {model_type} models found")
            return get_legacy_model_path()
        
        # Get highest version
        latest_version = max(versions)
        model_prefix = f"models/price_check_{model_type}{latest_version}/"
        
        logging.info(f"Using {model_type} model version {latest_version}: {model_prefix}")
        return model_prefix, latest_version
        
    except Exception as e:
        logging.error(f"Error getting latest model version: {e}")
        return get_legacy_model_path()

def get_legacy_model_path():
    """Fallback to old model path structure"""
    model_prefix = os.environ.get('MODEL_PREFIX', 'best_model')
    return f"{model_prefix}/", 0

def load_saved_artifacts():
    print("loading saved artifacts from S3...start")
    global __data_columns, __locations, __model
    
    bucket_name = os.environ.get('MLFLOW_S3_BUCKET', 'mlops-bucket0982')
    s3 = boto3.client('s3')
    
    # Get latest model version
    model_prefix, version = get_latest_model_version()
    
    # Build S3 keys
    columns_key = f"{model_prefix}columns.json"
    model_key = f"{model_prefix}banglore_home_prices_model.pickle"
    
    # Load columns.json from S3
    columns_obj = s3.get_object(Bucket=bucket_name, Key=columns_key)
    __data_columns = json.loads(columns_obj['Body'].read())['data_columns']
    __locations = __data_columns[3:]  # first 3 columns are sqft, bath, bhk
    # Expose the resolved model prefix so that the API layer can log the correct
    # variant (e.g. price_check_BO3 or price_check_CO2) without the leading path
    short_variant = model_prefix.strip('/')
    if short_variant.startswith('models/'):
        short_variant = short_variant[len('models/'):]  # remove leading directory
    os.environ["MODEL_PREFIX"] = short_variant
    
    # Load model from S3
    if __model is None:
        model_obj = s3.get_object(Bucket=bucket_name, Key=model_key)
        __model = pickle.load(BytesIO(model_obj['Body'].read()))
    
    print(f"loading saved artifacts from S3...done (version {version})")
    logging.info(f"Loaded model from {model_prefix} (version {version})")

def get_location_names():
    return __locations

def get_data_columns():
    return __data_columns

if __name__ == '__main__':
    load_saved_artifacts()
    print(get_location_names())
    print(get_estimated_price('1st Phase JP Nagar',1000, 3, 3))
    print(get_estimated_price('1st Phase JP Nagar', 1000, 2, 2))
    print(get_estimated_price('Kalhalli', 1000, 2, 2)) # other location
    print(get_estimated_price('Ejipura', 1000, 2, 2))  # other location