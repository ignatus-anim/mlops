"""Airflow DAG to generate candidate models with different hyperparameters."""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import Ridge, Lasso, ElasticNet
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import pickle
import json
import boto3
import os
import logging
from version_utils import get_latest_dataset_version, get_next_model_version, save_model_to_s3

DEFAULT_ARGS = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    dag_id="generate_candidate_dag",
    start_date=datetime(2025, 7, 21),
    schedule="@weekly",  # Generate new candidate weekly
    catchup=False,
    default_args=DEFAULT_ARGS,
)

BUCKET = os.getenv("MLFLOW_S3_BUCKET", "mlops-bucket0982")

def generate_candidate_model(**context):
    """Train a candidate model with different hyperparameters or algorithm"""
    
    # Get latest dataset version
    dataset_version, dataset_key = get_latest_dataset_version()
    logging.info(f"Using dataset version {dataset_version}: {dataset_key}")
    
    # Load data
    s3 = boto3.client('s3')
    data_obj = s3.get_object(Bucket=BUCKET, Key=dataset_key)
    df = pd.read_csv(data_obj['Body'])
    
    logging.info(f"Loaded {len(df)} rows for candidate training")
    
    # Prepare features
    X = df.drop(['price'], axis=1)
    y = df['price']
    
    # Different model configurations to try
    candidate_configs = [
        {
            "name": "ridge_tuned",
            "model": Ridge(alpha=0.1),  # Different alpha than production
            "scaler": StandardScaler()
        },
        {
            "name": "elastic_net",
            "model": ElasticNet(alpha=0.1, l1_ratio=0.5),
            "scaler": StandardScaler()
        },
        {
            "name": "random_forest",
            "model": RandomForestRegressor(n_estimators=50, random_state=42),
            "scaler": None  # RF doesn't need scaling
        },
        {
            "name": "ridge_no_scale",
            "model": Ridge(alpha=1.0),  # No scaling, different alpha
            "scaler": None
        }
    ]
    
    # Select a config (rotate weekly or use best performer)
    week_number = datetime.now().isocalendar()[1]
    config = candidate_configs[week_number % len(candidate_configs)]
    
    logging.info(f"Training candidate model: {config['name']}")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Apply scaling if needed
    if config['scaler']:
        X_train = config['scaler'].fit_transform(X_train)
        X_test = config['scaler'].transform(X_test)
    
    # Train model
    model = config['model']
    model.fit(X_train, y_train)
    
    # Evaluate
    train_score = model.score(X_train, y_train)
    test_score = model.score(X_test, y_test)
    
    logging.info(f"Candidate model scores - Train: {train_score:.3f}, Test: {test_score:.3f}")
    
    # Get next candidate version
    candidate_version, candidate_prefix = get_next_model_version('CO')
    
    # Prepare model data
    model_buffer = pickle.dumps(model)
    columns_data = {"data_columns": list(X.columns)}
    metadata = {
        "model_type": config['name'],
        "train_score": train_score,
        "test_score": test_score,
        "training_date": datetime.now().isoformat(),
        "data_rows": len(df),
        "dataset_version": dataset_version,
        "candidate_version": candidate_version
    }
    
    # Save versioned candidate model
    save_model_to_s3(model_buffer, columns_data, metadata, 'CO', candidate_version)
    
    logging.info(f"Generated candidate CO{candidate_version}: {config['name']}")
    return f"Generated candidate CO{candidate_version}: {config['name']}"

generate_task = PythonOperator(
    task_id="generate_candidate",
    python_callable=generate_candidate_model,
    dag=dag,
)
