from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
import os
import sys
import logging

# Add the dags directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import versioning utilities
from version_utils import (
    get_latest_dataset_version,
    get_next_model_version,
    get_latest_model_version,
    save_model_to_s3,
)

# Wrapper functions to delay imports until task execution
def preprocess_wrapper(**kwargs):
    from preprocess import preprocess_data
    # Only pass expected parameters
    expected_keys = {'input_path', 'output_path'}
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in expected_keys}
    return preprocess_data(**filtered_kwargs)

def train_wrapper(**kwargs):
    from train_model import train_model
    # Only pass expected parameters
    expected_keys = {'input_path', 'model_path', 'columns_path', 'track_with_mlflow', 'mlflow_experiment_name'}
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in expected_keys}
    return train_model(**filtered_kwargs)

def validation_wrapper(**kwargs):
    from validate_model import run_validation
    # Only pass expected parameters
    expected_keys = {'model_path', 'test_data_path', 'output_dir', 'track_with_mlflow', 'mlflow_experiment_name'}
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in expected_keys}
    return run_validation(**filtered_kwargs)

# ------------------------------------------------------------------
# Determine whether this run should generate a BO (best) or CO (candidate)
# ------------------------------------------------------------------
try:
    latest_bo_version, _ = get_latest_model_version('BO')
except Exception:
    latest_bo_version = 0

MODEL_TYPE = 'BO' if latest_bo_version == 0 else 'CO'
print(f"[bangalore_home_prices_dag] Running as model_type={MODEL_TYPE}")

# Define default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=5),
}

# Get configuration from environment variables
S3_BUCKET = os.environ.get('MLFLOW_S3_BUCKET', 'mlops-bucket0982')
S3_REGION = os.environ.get('AWS_DEFAULT_REGION', 'eu-west-1')

# Dynamic paths using versioning
def get_versioned_paths():
    """Return dataset info and next model prefix for the resolved MODEL_TYPE"""
    dataset_version, dataset_path = get_latest_dataset_version()
    model_version, model_prefix = get_next_model_version(MODEL_TYPE)
    return {
        'dataset_path': dataset_path,
        'dataset_version': dataset_version,
        'model_version': model_version,
        'model_prefix': model_prefix,
        'model_type': MODEL_TYPE,
    }

def get_dataset_version_from_path(dataset_path: str) -> int:
    """Extract version number from dataset path"""
    if "train_V" in dataset_path:
        import re
        match = re.search(r'train_V(\d+)\.csv', dataset_path)
        return int(match.group(1)) if match else 1
    return 1
# # Legacy paths for fallback
# S3_RAW_DATA_PATH = 'data/raw/train.csv'
# S3_PROCESSED_DATA_PATH = 'data/processed/preprocessed_data.csv'
# S3_MODEL_PATH = 'models/banglore_home_prices_model.pickle'
# S3_COLUMNS_PATH = 'models/columns.json'
# S3_VALIDATION_DIR = 'models/validation'

# MLflow configuration
MLFLOW_TRACKING_URI = os.environ.get('MLFLOW_TRACKING_URI', 'http://mlflow:5000')
MLFLOW_EXPERIMENT_NAME = os.environ.get('MLFLOW_EXPERIMENT_NAME', 'bangalore_home_prices')

# Set the tracking URI for all tasks
os.environ['MLFLOW_TRACKING_URI'] = MLFLOW_TRACKING_URI
logging.info(f"Using MLflow tracking URI: {MLFLOW_TRACKING_URI}")

# Create the DAG
dag = DAG(
    'bangalore_home_prices_pipeline',
    default_args=default_args,
    description='A DAG to automate the Bangalore home prices ML pipeline',
    schedule=timedelta(days=7),
    start_date=datetime(2025, 7, 20),
    catchup=False,
    tags=['machine_learning', 'real_estate', 'bangalore'],
)

# Task 1: Check if raw data exists in S3
def check_s3_data(**kwargs):
    from airflow.providers.amazon.aws.hooks.s3 import S3Hook
    from botocore.exceptions import ClientError
    
    s3_hook = S3Hook(aws_conn_id='aws_default')
    try:
        # First check if bucket exists and is accessible
        s3_hook.get_bucket(S3_BUCKET)
        print(f"Bucket {S3_BUCKET} is accessible")
        
        # Get latest dataset path using versioning system
        paths = get_versioned_paths()
        dataset_path = paths['dataset_path']
        
        # Check for the versioned dataset file
        if s3_hook.check_for_key(key=dataset_path, bucket_name=S3_BUCKET):
            print(f"Dataset file found in S3: s3://{S3_BUCKET}/{dataset_path}")
            return True
        else:
            # Fallback to check for legacy raw data path
            legacy_path = 'data/raw/train.csv'
            if s3_hook.check_for_key(key=legacy_path, bucket_name=S3_BUCKET):
                print(f"Legacy raw data file found in S3: s3://{S3_BUCKET}/{legacy_path}")
                print("Note: Using legacy path. Consider uploading versioned dataset.")
                return True
            else:
                raise FileNotFoundError(f"No dataset found in S3. Checked: {dataset_path} and {legacy_path}")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '403':
            raise PermissionError(f"Access denied to S3 bucket {S3_BUCKET}. Check AWS credentials and bucket permissions.")
        elif error_code == '404':
            raise FileNotFoundError(f"S3 bucket {S3_BUCKET} not found or not accessible.")
        else:
            raise e

check_data_task = PythonOperator(
    task_id='check_raw_data',
    python_callable=check_s3_data,
    dag=dag,
)

# Task 2: Preprocess the data (using versioned paths)
def preprocess_with_versioning(**context):
    """Preprocess data using latest dataset version"""
    paths = get_versioned_paths()
    from preprocess import preprocess_data
    
    # Use latest dataset and create corresponding preprocessed version
    dataset_version = paths['dataset_version']
    input_path = f's3://{S3_BUCKET}/{paths["dataset_path"]}'
    output_path = f's3://{S3_BUCKET}/data/processed/preprocessed_data_V{dataset_version}.csv'
    
    return preprocess_data(input_path=input_path, output_path=output_path)

preprocess_task = PythonOperator(
    task_id='preprocess_data',
    python_callable=preprocess_with_versioning,
    dag=dag,
)

# Task 3: Train the model with versioning
def train_with_versioning(**context):
    """Train model using versioned paths"""
    paths = get_versioned_paths()
    from train_model import train_model
    from airflow.providers.amazon.aws.hooks.s3 import S3Hook
    
    # Use preprocessed data file (not raw training data)
    dataset_version = paths['dataset_version']
    input_path = f's3://{S3_BUCKET}/data/processed/preprocessed_data_V{dataset_version}.csv'
    model_path = f's3://{S3_BUCKET}/{paths["model_prefix"]}banglore_home_prices_model.pickle'
    columns_path = f's3://{S3_BUCKET}/{paths["model_prefix"]}columns.json'
    
    print(f"Training model with:")
    print(f"  Input: {input_path}")
    print(f"  Model output: {model_path}")
    print(f"  Columns output: {columns_path}")
    
    result = train_model(
        input_path=input_path,
        model_path=model_path,
        columns_path=columns_path,
        track_with_mlflow=True,
        mlflow_experiment_name=MLFLOW_EXPERIMENT_NAME,

    )
    
    # Verify model was saved successfully
    s3_hook = S3Hook(aws_conn_id='aws_default')
    model_key = f"{paths['model_prefix']}banglore_home_prices_model.pickle"
    
    if not s3_hook.check_for_key(key=model_key, bucket_name=S3_BUCKET):
        raise RuntimeError(f"Training completed but model file not found: s3://{S3_BUCKET}/{model_key}")
    
    print(f"✅ Model successfully saved to: s3://{S3_BUCKET}/{model_key}")
    
    # Store paths in XCom for downstream tasks
    context['task_instance'].xcom_push(key='model_paths', value=paths)
    return result

train_model_task = PythonOperator(
    task_id='train_model',
    python_callable=train_with_versioning,
    dag=dag,
)

# Task 4: Validate the model with versioning
def validate_with_versioning(**context):
    """Validate model using versioned paths"""
    # Get paths from upstream task to ensure consistency
    paths = context['task_instance'].xcom_pull(task_ids='train_model', key='model_paths')
    if not paths:
        # Fallback to getting paths again if XCom failed
        paths = get_versioned_paths()
        print("Warning: Using fallback versioning - may cause inconsistency")
    
    from validate_model import run_validation
    from airflow.providers.amazon.aws.hooks.s3 import S3Hook
    
    # Use preprocessed data file for validation
    dataset_version = paths['dataset_version']
    model_path = f's3://{S3_BUCKET}/{paths["model_prefix"]}banglore_home_prices_model.pickle'
    test_data_path = f's3://{S3_BUCKET}/data/processed/preprocessed_data_V{dataset_version}.csv'
    output_dir = f's3://{S3_BUCKET}/{paths["model_prefix"]}validation/'
    
    # Check if model file exists before validation
    s3_hook = S3Hook(aws_conn_id='aws_default')
    model_key = f"{paths['model_prefix']}banglore_home_prices_model.pickle"
    
    if not s3_hook.check_for_key(key=model_key, bucket_name=S3_BUCKET):
        raise FileNotFoundError(f"Model file not found: s3://{S3_BUCKET}/{model_key}. Training may have failed.")
    
    print(f"Model file found: s3://{S3_BUCKET}/{model_key}")
    print(f"Validating with test data: {test_data_path}")
    
    return run_validation(
        model_path=model_path,
        test_data_path=test_data_path,
        output_dir=output_dir,
        track_with_mlflow=True,
        mlflow_experiment_name=MLFLOW_EXPERIMENT_NAME
    )

validation_task = PythonOperator(
    task_id='validate_model',
    python_callable=validate_with_versioning,
    dag=dag,
)

# Task 5: Log model metrics
def log_s3_metrics(**context):
    print(f"Model training completed at {datetime.now()}")
    
    # Get paths from upstream task to ensure consistency
    paths = context['task_instance'].xcom_pull(task_ids='train_model', key='model_paths')
    if not paths:
        # Fallback to getting paths again if XCom failed
        paths = get_versioned_paths()
        print("Warning: Using fallback versioning for logging")
    
    dataset_version = paths['dataset_version']
    print(f"Model saved to s3://{S3_BUCKET}/{paths['model_prefix']}banglore_home_prices_model.pickle")
    print(f"Columns saved to s3://{S3_BUCKET}/{paths['model_prefix']}columns.json")
    print(f"Validation results in s3://{S3_BUCKET}/{paths['model_prefix']}validation/")
    print(f"Model version: {paths['model_version']} ({paths['model_prefix']})")
    print(f"Model type: {paths['model_type']}")
    print(f"Dataset version: V{dataset_version} (from {paths['dataset_path']})")
    print(f"Preprocessed data: s3://{S3_BUCKET}/data/processed/preprocessed_data_V{dataset_version}.csv")

log_metrics_task = PythonOperator(
    task_id='log_model_metrics',
    python_callable=log_s3_metrics,
    dag=dag,
)

# Define task dependencies
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

if MODEL_TYPE == 'CO':
    # Copy candidate artifacts to candidate_model shortcut folder
    def copy_to_candidate_root(**kwargs):
        import boto3, os, re
        bucket = os.environ.get('MLFLOW_S3_BUCKET', 'mlops-bucket0982')
        s3_client = boto3.client('s3')
        # Find latest CO version in models folder
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix='models/price_check_CO')
        versions = []
        if 'Contents' in response:
            for obj in response['Contents']:
                m = re.search(r'models/price_check_CO(\d+)/', obj['Key'])
                if m:
                    versions.append(int(m.group(1)))
        if not versions:
            raise ValueError('No candidate models found to copy')
        latest = max(versions)
        prefix = f'models/price_check_CO{latest}/'
        s3 = boto3.resource('s3')
        candidate_root = 'candidate_model/'
        objects_to_copy = [
            f"{prefix}banglore_home_prices_model.pickle",
            f"{prefix}columns.json",
        ]
        for key in objects_to_copy:
            copy_source = {'Bucket': bucket, 'Key': key}
            dest_key = candidate_root + key.split('/')[-1]
            s3.Object(bucket, dest_key).copy(copy_source)
    
    copy_candidate = PythonOperator(
        task_id='copy_candidate_to_root',
        python_callable=copy_to_candidate_root,
        dag=dag,
    )

    # Restart candidate inference container so it picks up the new model
    restart_cand = BashOperator(
        task_id='restart_infer_cand',
        bash_command='docker compose restart infer-cand',
        dag=dag,
    )

    # Trigger evaluation DAG
    trigger_eval = TriggerDagRunOperator(
        task_id='trigger_evaluate_ab',
        trigger_dag_id='evaluate_ab_dag',
        dag=dag,
    )

    check_data_task >> preprocess_task >> train_model_task >> validation_task >> log_metrics_task >> copy_candidate >> restart_cand >> trigger_eval
else:
    end = EmptyOperator(task_id='end', dag=dag)
    check_data_task >> preprocess_task >> train_model_task >> validation_task >> log_metrics_task >> end
