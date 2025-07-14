import pandas as pd
import numpy as np
import pickle
import json
import os
import logging
from s3_utils import read_csv_from_s3, save_pickle_to_s3, save_json_to_s3

# Optional mlflow imports
try:
    import mlflow
    import mlflow.sklearn
    from mlflow_utils import setup_mlflow, start_run, log_params_and_metrics, log_model, log_artifacts, end_run
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
# sklearn imports moved inside functions to handle missing dependency

def prepare_features(df):
    """
    Prepare features for model training
    """
    logging.info("Preparing features...")
    
    # One-hot encoding for location
    dummies = pd.get_dummies(df.location)
    df_with_dummies = pd.concat([df, dummies.drop('other', axis='columns')], axis='columns')
    
    # Drop original location column
    df_processed = df_with_dummies.drop(['location'], axis='columns')
    
    return df_processed

def split_data(df):
    """
    Split data into training and testing sets
    """
    from sklearn.model_selection import train_test_split
    
    logging.info("Splitting data into train and test sets...")
    X = df.drop(['price'], axis='columns')
    y = df.price
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    return X_train, X_test, y_train, y_test

def get_algorithms():
    """Define algorithms and their hyperparameters"""
    from sklearn.linear_model import LinearRegression, Lasso, Ridge
    from sklearn.tree import DecisionTreeRegressor
    from sklearn.ensemble import RandomForestRegressor
    
    return {
        'linear_regression': {'model': LinearRegression(), 'params': {}},
        'lasso': {'model': Lasso(), 'params': {'alpha': [0.1, 1, 10]}},
        'ridge': {'model': Ridge(), 'params': {'alpha': [0.1, 1, 10]}},
        'decision_tree': {'model': DecisionTreeRegressor(), 'params': {'max_depth': [5, 10, 15]}},
        'random_forest': {'model': RandomForestRegressor(), 'params': {'n_estimators': [50, 100], 'max_depth': [5, 10]}}
    }

def train_and_evaluate_model(X_train, X_test, y_train, y_test, model_name, model, params):
    """Train and evaluate a single model"""
    from sklearn.model_selection import GridSearchCV
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    
    logging.info(f"Training {model_name}...")
    
    if params:
        grid_search = GridSearchCV(model, params, cv=3, scoring='neg_mean_squared_error')
        grid_search.fit(X_train, y_train)
        best_model = grid_search.best_estimator_
        best_params = grid_search.best_params_
    else:
        best_model = model
        best_model.fit(X_train, y_train)
        best_params = {}
    
    y_pred = best_model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    
    metrics = {'mse': mse, 'rmse': rmse, 'mae': mae, 'r2': r2}
    logging.info(f"{model_name} - RMSE: {rmse:.4f}, R²: {r2:.4f}")
    
    return best_model, best_params, metrics

def save_model(model, model_path):
    """
    Save the trained model to disk
    """
    logging.info(f"Saving model to {model_path}")
    save_pickle_to_s3(model, model_path)

def save_columns(X, columns_path):
    """
    Save column information for future predictions
    """
    logging.info(f"Saving columns information to {columns_path}")
    columns = {
        'data_columns': [col.lower() for col in X.columns]
    }
    save_json_to_s3(columns, columns_path)

def train_model(input_path, model_path, columns_path, track_with_mlflow=True, mlflow_experiment_name='bangalore_home_prices'):
    """Train multiple models and log experiments with MLflow"""
    logging.info("Starting model training...")
    
    # Check if sklearn is available
    try:
        import sklearn
    except ImportError:
        logging.error("scikit-learn is not installed. Please install it to use model training functionality.")
        raise ImportError("scikit-learn is required for model training but is not installed.")
    
    df = read_csv_from_s3(input_path)
    df_processed = prepare_features(df)
    X_train, X_test, y_train, y_test = split_data(df_processed)
    
    # Set up MLflow if tracking is enabled
    if track_with_mlflow and MLFLOW_AVAILABLE:
        from mlflow_utils import setup_mlflow, start_run, end_run, log_environment_info, log_git_info, log_data_info
        setup_mlflow(mlflow_experiment_name)
        
        # Log environment and git information for reproducibility
        log_environment_info()
        try:
            log_git_info()
        except Exception as e:
            logging.warning(f"Could not log git info: {str(e)}")
        
        # Log data information for reproducibility
        try:
            log_data_info(X_train, "training")
            log_data_info(X_test, "test")
        except Exception as e:
            logging.warning(f"Could not log data info: {str(e)}")
    elif track_with_mlflow and not MLFLOW_AVAILABLE:
        logging.warning("MLflow not available, skipping MLflow tracking")
        track_with_mlflow = False
    
    algorithms = get_algorithms()
    results = {}
    best_model = None
    best_score = float('-inf')
    best_model_name = None
    
    for model_name, config in algorithms.items():
        try:
            if track_with_mlflow and MLFLOW_AVAILABLE:
                start_run(run_name=f"{model_name}_training")
            
            model, best_params, metrics = train_and_evaluate_model(
                X_train, X_test, y_train, y_test,
                model_name, config['model'], config['params']
            )
            
            results[model_name] = {'model': model, 'params': best_params, 'metrics': metrics}
            
            # Already handled above
            
            if track_with_mlflow:
                # Log all parameters, not just the best ones
                mlflow.log_param('model_type', model_name)
                mlflow.log_param('algorithm', model.__class__.__name__)
                
                # Log all hyperparameters
                mlflow.log_params(best_params)
                
                # Log all default parameters that weren't tuned
                all_params = model.get_params()
                for param_name, param_value in all_params.items():
                    if param_name not in best_params:
                        mlflow.log_param(f"default_{param_name}", param_value)
                
                # Log metrics
                mlflow.log_metrics(metrics)
                
                # Log the model
                mlflow.sklearn.log_model(model, name=f"{model_name}_model")
                
                # Save model pickle to S3 as an artifact
                model_pickle_path = f"/tmp/{model_name}_model.pickle"
                with open(model_pickle_path, 'wb') as f:
                    pickle.dump(model, f)
                mlflow.log_artifact(model_pickle_path)
                
        except Exception as e:
            logging.error(f"Error training {model_name}: {str(e)}")
        finally:
            if track_with_mlflow and MLFLOW_AVAILABLE:
                end_run()
    
    if best_model:
        save_model(best_model, model_path)
        save_columns(df_processed.drop(['price'], axis='columns'), columns_path)
        logging.info(f"Best model ({best_model_name}) saved with R² score: {best_score:.4f}")
        logging.info(f"Training completed. Trained {len(results)} models.")
    
    return None

if __name__ == "__main__":
    # For testing
    input_file = "../../data/processed/preprocessed_data.csv"
    model_file = "../../models/banglore_home_prices_model.pickle"
    columns_file = "../../models/columns.json"
    train_model(input_file, model_file, columns_file)