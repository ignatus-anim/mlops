import pandas as pd
import numpy as np
import pickle
import json
import os
import logging
import matplotlib.pyplot as plt
from s3_utils import read_csv_from_s3, load_pickle_from_s3, save_json_to_s3, parse_s3_path, get_s3_client
from io import BytesIO

# Optional mlflow imports
try:
    import mlflow
    from mlflow_utils import setup_mlflow, start_run, log_params_and_metrics, log_artifacts, end_run
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

def load_model(model_path):
    """
    Load the trained model from disk
    """
    logging.info(f"Loading model from {model_path}")
    return load_pickle_from_s3(model_path)

def preprocess_validation_data(df):
    """
    Preprocess validation data same as training data
    """
    # One-hot encoding for location
    dummies = pd.get_dummies(df.location)
    df_with_dummies = pd.concat([df, dummies.drop('other', axis='columns')], axis='columns')
    
    # Drop original location column
    df_processed = df_with_dummies.drop(['location'], axis='columns')
    
    return df_processed

def validate_model(model, test_data_path, output_dir):
    """
    Validate model performance on test data and generate evaluation metrics
    """
    logging.info("Starting model validation...")
    
    # Load test data
    df = read_csv_from_s3(test_data_path)
    
    # Preprocess validation data
    df_processed = preprocess_validation_data(df)
    
    # Prepare features
    X = df_processed.drop(['price'], axis='columns')
    y_true = df_processed.price
    
    # Make predictions
    y_pred = model.predict(X)
    
    # Calculate metrics
    mse = mean_squared_error(y_true, y_pred)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    
    logging.info(f"Model Metrics - RMSE: {rmse}, MAE: {mae}, R²: {r2}")
    
    # Create validation report
    metrics = {
        'mse': mse,
        'rmse': rmse,
        'mae': mae,
        'r2': r2,
        'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Save metrics to file
    bucket, key_prefix = parse_s3_path(output_dir)
    if bucket:
        metrics_key = f"{key_prefix}/model_metrics.json" if key_prefix else "model_metrics.json"
        metrics_path = f"s3://{bucket}/{metrics_key}"
    else:
        metrics_path = os.path.join(output_dir, 'model_metrics.json')
    
    save_json_to_s3(metrics, metrics_path)
    
    # Generate validation plots
    generate_validation_plots(y_true, y_pred, output_dir)
    
    logging.info(f"Validation metrics saved to {metrics_path}")
    return metrics

def save_plot_to_s3(fig, s3_path, region='eu-west-1'):
    """Save matplotlib figure to S3"""
    bucket, key = parse_s3_path(s3_path)
    if bucket is None:
        fig.savefig(s3_path)
        return
    
    s3 = get_s3_client(region)
    img_buffer = BytesIO()
    fig.savefig(img_buffer, format='png')
    img_buffer.seek(0)
    s3.put_object(Bucket=bucket, Key=key, Body=img_buffer.getvalue())

def generate_validation_plots(y_true, y_pred, output_dir):
    """
    Generate plots for model validation
    """
    bucket, key_prefix = parse_s3_path(output_dir)
    
    # Create scatter plot of actual vs predicted values
    fig1 = plt.figure(figsize=(10, 6))
    plt.scatter(y_true, y_pred, alpha=0.5)
    plt.plot([min(y_true), max(y_true)], [min(y_true), max(y_true)], 'r--')
    plt.xlabel('Actual Price')
    plt.ylabel('Predicted Price')
    plt.title('Actual vs Predicted Home Prices')
    
    # Save plot
    if bucket:
        plot_key = f"{key_prefix}/actual_vs_predicted.png" if key_prefix else "actual_vs_predicted.png"
        plot_path = f"s3://{bucket}/{plot_key}"
    else:
        plot_path = os.path.join(output_dir, 'actual_vs_predicted.png')
    
    save_plot_to_s3(fig1, plot_path)
    plt.close(fig1)
    
    # Create residual plot
    residuals = y_true - y_pred
    fig2 = plt.figure(figsize=(10, 6))
    plt.scatter(y_pred, residuals, alpha=0.5)
    plt.axhline(y=0, color='r', linestyle='--')
    plt.xlabel('Predicted Price')
    plt.ylabel('Residuals')
    plt.title('Residual Plot')
    
    # Save plot
    if bucket:
        residual_key = f"{key_prefix}/residual_plot.png" if key_prefix else "residual_plot.png"
        residual_path = f"s3://{bucket}/{residual_key}"
    else:
        residual_path = os.path.join(output_dir, 'residual_plot.png')
    
    save_plot_to_s3(fig2, residual_path)
    plt.close(fig2)
    
    logging.info(f"Validation plots saved to {output_dir}")

def run_validation(model_path, test_data_path, output_dir, track_with_mlflow=True, mlflow_experiment_name='bangalore_home_prices'):
    """
    Main function to run model validation
    """
    # Ensure output directory exists (only for local paths)
    bucket, key = parse_s3_path(output_dir)
    if bucket is None:
        os.makedirs(output_dir, exist_ok=True)
    
    # Set up MLflow tracking if enabled
    if track_with_mlflow and MLFLOW_AVAILABLE:
        setup_mlflow(mlflow_experiment_name)
        start_run(run_name=f"model_validation_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}")
    elif track_with_mlflow and not MLFLOW_AVAILABLE:
        logging.warning("MLflow not available, skipping MLflow tracking")
        track_with_mlflow = False
    
    try:
        # Load model
        model = load_model(model_path)
        
        # Validate model
        metrics = validate_model(model, test_data_path, output_dir)
        
        # Log validation metrics to MLflow
        if track_with_mlflow:
            # Log parameters
            params = {
                'validation_data': test_data_path,
                'model_path': model_path
            }
            
            # Log metrics
            log_params_and_metrics(params, metrics)
            
            # Log validation plots as artifacts
            plot_paths = [
                os.path.join(output_dir, 'actual_vs_predicted.png'),
                os.path.join(output_dir, 'residual_plot.png'),
                os.path.join(output_dir, 'model_metrics.json')
            ]
            log_artifacts(plot_paths)
            
        return metrics
    
    finally:
        # End MLflow run if tracking is enabled
        if track_with_mlflow:
            end_run()

if __name__ == "__main__":
    # For testing
    model_file = "../../models/banglore_home_prices_model.pickle"
    test_data = "../../data/processed/validation.csv"
    output_dir = "../../models/validation"
    run_validation(model_file, test_data, output_dir)
