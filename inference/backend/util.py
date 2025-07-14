import pickle
import json
import numpy as np
import boto3
import os
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


def load_saved_artifacts():
    print("loading saved artifacts from S3...start")
    global __data_columns, __locations, __model
    
    bucket_name = os.environ.get('MLFLOW_S3_BUCKET', 'mlops-bucket0982')
    best_prefix = os.environ.get('BEST_MODEL_PREFIX', 'best_model')
    s3 = boto3.client('s3')
    
    # Build S3 keys
    columns_key = f"{best_prefix}/columns.json"
    model_key = f"{best_prefix}/banglore_home_prices_model.pickle"
    
    # Load columns.json from S3
    columns_obj = s3.get_object(Bucket=bucket_name, Key=columns_key)
    __data_columns = json.loads(columns_obj['Body'].read())['data_columns']
    __locations = __data_columns[3:]  # first 3 columns are sqft, bath, bhk
    
    # Load model from S3
    if __model is None:
        model_obj = s3.get_object(Bucket=bucket_name, Key=model_key)
        __model = pickle.load(BytesIO(model_obj['Body'].read()))
    
    print("loading saved artifacts from S3...done")

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