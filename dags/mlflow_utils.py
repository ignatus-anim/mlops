import mlflow
import mlflow.sklearn
import os
import logging
import sys
import platform
import subprocess
import hashlib
import pandas as pd
import json
from datetime import datetime

def setup_mlflow(experiment_name, tracking_uri=None):
    """
    Set up MLflow tracking
    
    Args:
        experiment_name: Name of the MLflow experiment
        tracking_uri: URI of the MLflow tracking server (optional)
    """
    # Set tracking URI if provided
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    else:
        # Use the environment variable MLFLOW_TRACKING_URI if available
        # This ensures consistent configuration across the application
        env_uri = os.environ.get('MLFLOW_TRACKING_URI', 'http://mlflow:5000')
        mlflow.set_tracking_uri(env_uri)
        logging.info(f"MLflow tracking URI set to: {env_uri}")

    # Get or create the experiment
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        experiment_id = mlflow.create_experiment(experiment_name)
        logging.info(f"Created new MLflow experiment: {experiment_name}")
    else:
        experiment_id = experiment.experiment_id
        logging.info(f"Using existing MLflow experiment: {experiment_name}")

    # Set this experiment as the default for forthcoming runs
    mlflow.set_experiment(experiment_name)
    return experiment_id

def log_params_and_metrics(params, metrics):
    """
    Log parameters and metrics to MLflow
    
    Args:
        params: Dictionary of parameters to log
        metrics: Dictionary of metrics to log
    """
    # Log parameters
    for param_name, param_value in params.items():
        mlflow.log_param(param_name, param_value)
    
    # Log metrics (exclude non-numeric values like timestamp)
    for metric_name, metric_value in metrics.items():
        if isinstance(metric_value, (int, float)):
            mlflow.log_metric(metric_name, metric_value)
    
    logging.info("Parameters and metrics logged to MLflow")

def log_model(model, model_name):
    """
    Log the trained model to MLflow
    
    Args:
        model: Trained model object
        model_name: Name to give the model in MLflow
    """
    mlflow.sklearn.log_model(model, model_name)
    logging.info(f"Model logged to MLflow as {model_name}")

def log_artifacts(artifact_paths):
    """
    Log artifacts to MLflow
    
    Args:
        artifact_paths: List of file paths to log as artifacts
    """
    for path in artifact_paths:
        if os.path.exists(path):
            mlflow.log_artifact(path)
            logging.info(f"Artifact logged to MLflow: {path}")
        else:
            logging.warning(f"Artifact path not found: {path}")

def start_run(run_name=None):
    """
    Start a new MLflow run
    
    Args:
        run_name: Optional name for the run
    
    Returns:
        run: MLflow run object
    """
    if run_name is None:
        run_name = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # End any existing active run to avoid conflicts when nested calls happen
    if mlflow.active_run() is not None:
        mlflow.end_run()
    run = mlflow.start_run(run_name=run_name)
    logging.info(f"Started MLflow run: {run_name}")
    return run

def log_environment_info():
    """
    Log information about the execution environment to MLflow
    """
    # Log Python version
    mlflow.log_param("python_version", platform.python_version())
    
    # Log system info
    mlflow.log_param("os", platform.system())
    mlflow.log_param("os_release", platform.release())
    
    # Log key package versions
    try:
        import sklearn
        mlflow.log_param("sklearn_version", sklearn.__version__)
    except (ImportError, AttributeError):
        pass
    
    try:
        import pandas
        mlflow.log_param("pandas_version", pandas.__version__)
    except (ImportError, AttributeError):
        pass
    
    try:
        import numpy
        mlflow.log_param("numpy_version", numpy.__version__)
    except (ImportError, AttributeError):
        pass
    
    # Log all installed packages as an artifact
    try:
        reqs = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'])
        requirements_path = "/tmp/requirements.txt"
        with open(requirements_path, 'wb') as f:
            f.write(reqs)
        mlflow.log_artifact(requirements_path, "environment")
        logging.info("Logged environment information to MLflow")
    except Exception as e:
        logging.warning(f"Failed to log pip packages: {str(e)}")

def log_git_info():
    """
    Log Git repository information to MLflow
    """
    # If not in a git repository, skip quietly
    if not os.path.exists('.git'):
        logging.info('No .git directory found; skipping git info logging')
        return
    try:
        # Get git commit hash
        git_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()
        mlflow.log_param("git_commit", git_commit)
        
        # Get git branch
        git_branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).decode('ascii').strip()
        mlflow.log_param("git_branch", git_branch)
        
        # Check if working directory is clean
        git_status = subprocess.check_output(['git', 'status', '--porcelain']).decode('ascii').strip()
        is_dirty = len(git_status) > 0
        mlflow.log_param("git_is_dirty", is_dirty)
        
        logging.info("Logged Git information to MLflow")
    except Exception as e:
        logging.warning(f"Failed to log git info: {str(e)}")

def compute_data_hash(df):
    """
    Compute a hash of the dataframe to track data versions
    
    Args:
        df: Pandas DataFrame to hash
    
    Returns:
        hash_value: Hash string representing the data
    """
    try:
        # Convert DataFrame to string and hash it
        data_str = pd.util.hash_pandas_object(df).sum()
        hash_value = hashlib.md5(str(data_str).encode()).hexdigest()
        return hash_value
    except Exception as e:
        logging.warning(f"Failed to compute data hash: {str(e)}")
        return None

def log_data_info(df, data_name):
    """
    Log information about the dataset to MLflow
    
    Args:
        df: Pandas DataFrame to log info about
        data_name: Name of the dataset (e.g., 'training', 'validation')
    """
    try:
        # Log basic dataset stats
        mlflow.log_param(f"{data_name}_rows", df.shape[0])
        mlflow.log_param(f"{data_name}_columns", df.shape[1])
        
        # Log column names
        mlflow.log_param(f"{data_name}_features", list(df.columns))
        
        # Log data hash for versioning
        data_hash = compute_data_hash(df)
        if data_hash:
            mlflow.log_param(f"{data_name}_hash", data_hash)
        
        # Log data summary as artifact
        summary_path = f"/tmp/{data_name}_summary.json"
        summary = {
            "shape": df.shape,
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "missing_values": df.isnull().sum().to_dict(),
            "hash": data_hash
        }
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        mlflow.log_artifact(summary_path, "data_info")
        
        logging.info(f"Logged {data_name} dataset information to MLflow")
    except Exception as e:
        logging.warning(f"Failed to log data info: {str(e)}")

def end_run():
    """
    End the current MLflow run
    """
    mlflow.end_run()
    logging.info("MLflow run ended")
