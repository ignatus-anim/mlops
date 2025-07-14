import boto3
import pandas as pd
import pickle
import json
import os
from io import StringIO, BytesIO

def get_s3_client(region='eu-west-1'):
    """Get S3 client with proper credentials"""
    try:
        from airflow.providers.amazon.aws.hooks.s3 import S3Hook
        s3_hook = S3Hook(aws_conn_id='aws_default')
        return s3_hook.get_conn()
    except ImportError:
        # Fallback to boto3 if not in Airflow environment
        return boto3.client('s3', region_name=region)

def parse_s3_path(s3_path):
    """Parse S3 path into bucket and key"""
    if not s3_path.startswith('s3://'):
        return None, s3_path  # Local path
    path_parts = s3_path[5:].split('/', 1)
    bucket = path_parts[0]
    key = path_parts[1] if len(path_parts) > 1 else ''
    return bucket, key

def read_csv_from_s3(s3_path, region='eu-west-1'):
    """Read CSV from S3 or local path"""
    bucket, key = parse_s3_path(s3_path)
    if bucket is None:
        return pd.read_csv(s3_path)
    
    s3 = get_s3_client(region)
    obj = s3.get_object(Bucket=bucket, Key=key)
    return pd.read_csv(obj['Body'])

def write_csv_to_s3(df, s3_path, region='eu-west-1'):
    """Write CSV to S3 or local path"""
    bucket, key = parse_s3_path(s3_path)
    if bucket is None:
        df.to_csv(s3_path, index=False)
        return
    
    s3 = get_s3_client(region)
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    s3.put_object(Bucket=bucket, Key=key, Body=csv_buffer.getvalue())

def save_pickle_to_s3(obj, s3_path, region='eu-west-1'):
    """Save pickle object to S3 or local path"""
    bucket, key = parse_s3_path(s3_path)
    if bucket is None:
        with open(s3_path, 'wb') as f:
            pickle.dump(obj, f)
        return
    
    s3 = get_s3_client(region)
    pickle_buffer = BytesIO()
    pickle.dump(obj, pickle_buffer)
    s3.put_object(Bucket=bucket, Key=key, Body=pickle_buffer.getvalue())

def load_pickle_from_s3(s3_path, region='eu-west-1'):
    """Load pickle object from S3 or local path"""
    bucket, key = parse_s3_path(s3_path)
    if bucket is None:
        with open(s3_path, 'rb') as f:
            return pickle.load(f)
    
    s3 = get_s3_client(region)
    obj = s3.get_object(Bucket=bucket, Key=key)
    return pickle.load(obj['Body'])

def save_json_to_s3(data, s3_path, region='eu-west-1'):
    """Save JSON to S3 or local path"""
    bucket, key = parse_s3_path(s3_path)
    if bucket is None:
        with open(s3_path, 'w') as f:
            json.dump(data, f)
        return
    
    s3 = get_s3_client(region)
    s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(data))

def load_json_from_s3(s3_path, region='eu-west-1'):
    """Load JSON from S3 or local path"""
    bucket, key = parse_s3_path(s3_path)
    if bucket is None:
        with open(s3_path, 'r') as f:
            return json.load(f)
    
    s3 = get_s3_client(region)
    obj = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(obj['Body'].read())