"""Shared utilities for model and dataset versioning across all DAGs."""
import boto3
import re
import logging
from typing import Optional, List, Tuple

BUCKET = "mlops-bucket0982"

def get_s3_client():
    """Get configured S3 client"""
    return boto3.client('s3')

def list_s3_objects_with_prefix(prefix: str) -> List[str]:
    """List all S3 objects with given prefix"""
    s3 = get_s3_client()
    try:
        response = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix)
        if 'Contents' in response:
            return [obj['Key'] for obj in response['Contents']]
        return []
    except Exception as e:
        logging.error(f"Error listing S3 objects with prefix {prefix}: {e}")
        return []

def extract_version_number(key: str, pattern: str) -> Optional[int]:
    """Extract version number from S3 key using regex pattern"""
    match = re.search(pattern, key)
    if match:
        return int(match.group(1))
    return None

def get_latest_dataset_version() -> Tuple[int, str]:
    """Get the latest dataset version number and full key"""
    # Prioritize raw data over processed data
    raw_keys = list_s3_objects_with_prefix("data/raw/train_V")
    
    # Extract version numbers from raw data: train_V(\d+)\.csv
    raw_versions = []
    for key in raw_keys:
        version = extract_version_number(key, r'train_V(\d+)\.csv')
        if version:
            raw_versions.append((version, key))
    
    if raw_versions:
        # Use highest version from raw data
        latest_version, latest_key = max(raw_versions, key=lambda x: x[0])
        logging.info(f"Latest dataset: {latest_key} (version {latest_version})")
        return latest_version, latest_key
    
    # Fallback to processed data if no raw data found
    processed_keys = list_s3_objects_with_prefix("data/processed/train_V")
    processed_versions = []
    for key in processed_keys:
        version = extract_version_number(key, r'train_V(\d+)\.csv')
        if version:
            processed_versions.append((version, key))
    
    if processed_versions:
        latest_version, latest_key = max(processed_versions, key=lambda x: x[0])
        logging.warning(f"No raw data found, using processed: {latest_key} (version {latest_version})")
        return latest_version, latest_key
    
    # No versioned datasets found
    logging.warning("No versioned datasets found, returning V1")
    return 1, "data/raw/train_V1.csv"

def get_latest_model_version(model_type: str) -> Tuple[int, str]:
    """Get latest model version for BO (best) or CO (candidate)"""
    if model_type not in ['BO', 'CO']:
        raise ValueError("model_type must be 'BO' or 'CO'")
    
    prefix = f"models/price_check_{model_type}"
    keys = list_s3_objects_with_prefix(prefix)
    
    if not keys:
        logging.warning(f"No {model_type} models found, returning version 1")
        return 1, f"models/price_check_{model_type}1/"
    
    # Extract version numbers: price_check_(BO|CO)(\d+)/
    versions = []
    for key in keys:
        version = extract_version_number(key, rf'price_check_{model_type}(\d+)/')
        if version:
            versions.append(version)
    
    if not versions:
        return 1, f"models/price_check_{model_type}1/"
    
    latest_version = max(versions)
    latest_prefix = f"models/price_check_{model_type}{latest_version}/"
    logging.info(f"Latest {model_type} model: {latest_prefix}")
    return latest_version, latest_prefix

def get_next_model_version(model_type: str) -> Tuple[int, str]:
    """Get next version number for new model"""
    latest_version, _ = get_latest_model_version(model_type)
    next_version = latest_version + 1
    next_prefix = f"models/price_check_{model_type}{next_version}/"
    return next_version, next_prefix

def save_model_to_s3(model_data: bytes, columns_data: dict, metadata: dict, 
                    model_type: str, version: int):
    """Save model, columns, and metadata to versioned S3 location"""
    s3 = get_s3_client()
    prefix = f"models/price_check_{model_type}{version}/"
    
    # Save model pickle
    s3.put_object(
        Bucket=BUCKET,
        Key=f"{prefix}banglore_home_prices_model.pickle",
        Body=model_data
    )
    
    # Save columns JSON
    import json
    s3.put_object(
        Bucket=BUCKET,
        Key=f"{prefix}columns.json",
        Body=json.dumps(columns_data)
    )
    
    # Save metadata
    s3.put_object(
        Bucket=BUCKET,
        Key=f"{prefix}metadata.json",
        Body=json.dumps(metadata)
    )
    
    logging.info(f"Saved {model_type} model version {version} to {prefix}")

def promote_candidate_to_best():
    """Copy latest candidate model to new best model version"""
    s3 = get_s3_client()
    
    # Get latest candidate
    cand_version, cand_prefix = get_latest_model_version('CO')
    
    # Get next best version
    next_best_version, next_best_prefix = get_next_model_version('BO')
    
    # Copy all files from candidate to new best
    cand_objects = list_s3_objects_with_prefix(cand_prefix)
    
    for obj_key in cand_objects:
        # Get relative path within the model folder
        rel_path = obj_key.replace(cand_prefix, '')
        new_key = next_best_prefix + rel_path
        
        # Copy object
        s3.copy_object(
            Bucket=BUCKET,
            CopySource={'Bucket': BUCKET, 'Key': obj_key},
            Key=new_key
        )
        logging.info(f"Copied {obj_key} -> {new_key}")
    
    logging.info(f"Promoted candidate CO{cand_version} to best BO{next_best_version}")
    return next_best_version, next_best_prefix
