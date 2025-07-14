from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
import os
import sys
import logging

# Add the dags directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

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

# S3 paths from environment variables
S3_RAW_DATA_PATH = os.environ.get('S3_RAW_DATA_PATH', 'data/raw/train.csv')
S3_PROCESSED_DATA_PATH = os.environ.get('S3_PROCESSED_DATA_PATH', 'data/processed/preprocessed_data.csv')
S3_MODEL_PATH = os.environ.get('S3_MODEL_PATH', 'models/banglore_home_prices_model.pickle')
S3_COLUMNS_PATH = os.environ.get('S3_COLUMNS_PATH', 'models/columns.json')
S3_VALIDATION_DIR = os.environ.get('S3_VALIDATION_DIR', 'models/validation')

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
    schedule=timedelta(days=7),  # Run weekly
    start_date=datetime(2023, 1, 1),
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
        
        # Then check for the specific file
        if s3_hook.check_for_key(key=S3_RAW_DATA_PATH, bucket_name=S3_BUCKET):
            print(f"Raw data file found in S3: s3://{S3_BUCKET}/{S3_RAW_DATA_PATH}")
            return True
        else:
            raise FileNotFoundError(f"Raw data not found in S3: s3://{S3_BUCKET}/{S3_RAW_DATA_PATH}")
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

# Task 2: Preprocess the data
preprocess_task = PythonOperator(
    task_id='preprocess_data',
    python_callable=preprocess_wrapper,
    op_kwargs={
        'input_path': f's3://{S3_BUCKET}/{S3_RAW_DATA_PATH}',
        'output_path': f's3://{S3_BUCKET}/{S3_PROCESSED_DATA_PATH}'
    },
    dag=dag,
)

# Task 3: Train the model with MLflow tracking
train_model_task = PythonOperator(
    task_id='train_model',
    python_callable=train_wrapper,
    op_kwargs={
        'input_path': f's3://{S3_BUCKET}/{S3_PROCESSED_DATA_PATH}',
        'model_path': f's3://{S3_BUCKET}/{S3_MODEL_PATH}',
        'columns_path': f's3://{S3_BUCKET}/{S3_COLUMNS_PATH}',
        'track_with_mlflow': True,
        'mlflow_experiment_name': MLFLOW_EXPERIMENT_NAME
    },
    dag=dag,
)

# Task 4: Validate the model with MLflow tracking
validate_model_task = PythonOperator(
    task_id='validate_model',
    python_callable=validation_wrapper,
    op_kwargs={
        'model_path': f's3://{S3_BUCKET}/{S3_MODEL_PATH}',
        'test_data_path': f's3://{S3_BUCKET}/{S3_PROCESSED_DATA_PATH}',
        'output_dir': f's3://{S3_BUCKET}/{S3_VALIDATION_DIR}',
        'track_with_mlflow': True,
        'mlflow_experiment_name': MLFLOW_EXPERIMENT_NAME
    },
    dag=dag,
)

# Task 5: Log model metrics
def log_s3_metrics(**kwargs):
    print(f"Model training completed at {datetime.now()}")
    print(f"Model saved to s3://{S3_BUCKET}/{S3_MODEL_PATH}")
    print(f"Columns saved to s3://{S3_BUCKET}/{S3_COLUMNS_PATH}")
    print(f"Validation results in s3://{S3_BUCKET}/{S3_VALIDATION_DIR}")

log_metrics_task = PythonOperator(
    task_id='log_model_metrics',
    python_callable=log_s3_metrics,
    dag=dag,
)

# Define task dependencies
check_data_task >> preprocess_task >> train_model_task >> validate_model_task >> log_metrics_task
