"""Airflow DAG to evaluate A/B prediction logs and promote candidate model."""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import boto3, os, subprocess, logging
from version_utils import get_latest_model_version, promote_candidate_to_best

DEFAULT_ARGS = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    dag_id="evaluate_ab_dag",
    start_date=datetime(2025, 7, 14),
    schedule="@hourly",
    catchup=False,
    default_args=DEFAULT_ARGS,
)

PG_USER = os.getenv("POSTGRES_USER", "airflow")
PG_PWD = os.getenv("POSTGRES_PASSWORD", "airflow")
PG_HOST = os.getenv("POSTGRES_HOST", "postgres")
PG_DB   = os.getenv("POSTGRES_DB", "airflow")
ENGINE_STR = f"postgresql+psycopg2://{PG_USER}:{PG_PWD}@{PG_HOST}/{PG_DB}"

BUCKET = os.getenv("MLFLOW_S3_BUCKET", "mlops-bucket0982")

# Dynamic prefixes based on latest versions
def get_current_model_prefixes():
    """Get current model prefixes for logging queries"""
    try:
        prod_version, prod_prefix = get_latest_model_version('BO')
        cand_version, cand_prefix = get_latest_model_version('CO')
        return {
            'prod_prefix': f'price_check_BO{prod_version}',
            'cand_prefix': f'price_check_CO{cand_version}',
            'prod_version': prod_version,
            'cand_version': cand_version
        }
    except Exception as e:
        logging.warning(f"Error getting model prefixes, using legacy: {e}")
        return {
            'prod_prefix': 'best_model',
            'cand_prefix': 'candidate_model',
            'prod_version': 0,
            'cand_version': 0
        }

def calculate_feedback_metrics(variant, days_back=7):
    """Calculate performance metrics based on user feedback"""
    engine = create_engine(ENGINE_STR)
    with engine.begin() as conn:
        # Get feedback data
        feedback_data = conn.execute(text("""
            SELECT 
                pl.variant,
                uf.feedback_type,
                uf.feedback_value,
                pl.prediction,
                CASE 
                    WHEN uf.feedback_type = 'actual_price' THEN uf.feedback_value
                    WHEN uf.feedback_type = 'rating' THEN uf.feedback_value
                    WHEN uf.feedback_type = 'accurate' THEN 5.0
                    WHEN uf.feedback_type = 'too_high' THEN 2.0
                    WHEN uf.feedback_type = 'too_low' THEN 2.0
                    ELSE NULL
                END as normalized_score
            FROM prediction_logs pl
            JOIN user_feedback uf ON pl.id = uf.prediction_id
            WHERE pl.variant = :variant 
              AND pl.ts > now() - interval '%s days'
        """) % days_back, {"variant": variant}).fetchall()
        
        if len(feedback_data) < 10:  # Need minimum feedback
            return None
            
        # Calculate metrics
        ratings = [row[4] for row in feedback_data if row[4] is not None]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0
        
        # Calculate MAE for actual price feedback
        actual_price_data = [(row[2], row[3]) for row in feedback_data if row[1] == 'actual_price']
        mae = None
        if len(actual_price_data) >= 5:
            errors = [abs(actual - pred) for actual, pred in actual_price_data]
            mae = sum(errors) / len(errors)
        
        return {
            "avg_rating": avg_rating,
            "mae": mae,
            "feedback_count": len(feedback_data),
            "actual_price_count": len(actual_price_data)
        }

def decide_promotion(**_):
    # Check for data drift first
    try:
        import sys
        sys.path.append('/opt/airflow/inference/backend')
        from drift_monitor import get_drift_summary
        
        drift_summary = get_drift_summary()
        if drift_summary.get('overall_drift_detected', False):
            logging.warning("⚠️  Data drift detected - consider retraining before promotion")
            drift_features = [f for f, i in drift_summary.get('drift_indicators', {}).items() 
                            if i.get('significant_drift', False)]
            logging.info(f"Drifted features: {drift_features}")
        else:
            logging.info("✅ No significant drift detected")
    except Exception as e:
        logging.warning(f"Drift check failed: {e}")
    
    # Get current model prefixes
    prefixes = get_current_model_prefixes()
    prod_prefix = prefixes['prod_prefix']
    cand_prefix = prefixes['cand_prefix']
    
    logging.info(f"Evaluating: {prod_prefix} vs {cand_prefix}")
    
    engine = create_engine(ENGINE_STR)
    with engine.begin() as conn:
        # Get request counts
        rows = conn.execute(text("""
            SELECT variant, COUNT(*) AS n
            FROM prediction_logs
            WHERE ts > now() - interval '1 day'
            GROUP BY variant
        """)).fetchall()
    
    counts = {r[0]: r[1] for r in rows}
    cand_n = counts.get(cand_prefix, 0)
    prod_n = counts.get(prod_prefix, 0)
    
    logging.info("Request counts 24h: %s", counts)
    
    # Need minimum traffic
    if cand_n < 50:
        logging.info("Not enough candidate traffic yet (need 50). Skipping.")
        return "skip"
    
    # Get feedback metrics
    prod_metrics = calculate_feedback_metrics(prod_prefix)
    cand_metrics = calculate_feedback_metrics(cand_prefix)
    
    logging.info("Production metrics: %s", prod_metrics)
    logging.info("Candidate metrics: %s", cand_metrics)
    
    # If we don't have enough feedback, use simple volume rule
    if not prod_metrics or not cand_metrics:
        if cand_n >= 100:
            logging.info("Insufficient feedback data, promoting based on volume")
            return "promote"
        return "skip"
    
    # Performance-based decision
    cand_rating = cand_metrics["avg_rating"]
    prod_rating = prod_metrics["avg_rating"]
    
    # Check for significant degradation (safety check)
    if cand_rating < prod_rating * 0.8:  # 20% worse rating
        logging.warning("Candidate rating significantly worse (%.2f vs %.2f) - rollback", 
                       cand_rating, prod_rating)
        return "rollback"
    
    # Check for improvement
    improvement_threshold = 0.1  # 10% improvement
    if cand_rating > prod_rating * (1 + improvement_threshold):
        logging.info("Candidate performing better (%.2f vs %.2f) - promoting", 
                    cand_rating, prod_rating)
        return "promote"
    
    # Check MAE if available
    if cand_metrics["mae"] and prod_metrics["mae"]:
        if cand_metrics["mae"] < prod_metrics["mae"] * 0.9:  # 10% better MAE
            logging.info("Candidate has better MAE (%.2f vs %.2f) - promoting", 
                        cand_metrics["mae"], prod_metrics["mae"])
            return "promote"
    
    # Check testing duration
    engine = create_engine(ENGINE_STR)
    with engine.begin() as conn:
        first_cand_request = conn.execute(text("""
            SELECT MIN(ts) FROM prediction_logs WHERE variant = :variant
        """), {"variant": cand_prefix}).fetchone()[0]
        
        if first_cand_request:
            from datetime import datetime, timezone
            days_testing = (datetime.now(timezone.utc) - first_cand_request).days
            if days_testing > 7:  # Max 1 week of testing
                logging.info("Candidate testing period expired (%d days), reverting", days_testing)
                return "rollback"
    
    logging.info("Candidate performance acceptable, continuing test")
    return "skip"

def promote_model(**_):
    """Promote latest candidate to new best model version"""
    try:
        # Use versioning utility to promote
        new_version, new_prefix = promote_candidate_to_best()
        
        logging.info(f"Promoted candidate to new best model BO{new_version}")
        
        # Restart prod container to pick up new model
        try:
            subprocess.check_call(["docker", "compose", "restart", "infer-prod"])
            logging.info("Restarted infer-prod container")
        except Exception as e:
            logging.warning("Could not restart infer-prod: %s", e)
        
        # Trigger training DAG again to possibly create next candidate when new dataset arrives
        from airflow.api.common.experimental.trigger_dag import trigger_dag
        try:
            trigger_dag("bangalore_home_prices_pipeline", run_id=f"trigger_after_promo_{datetime.utcnow().isoformat()}")
        except Exception as e:
            logging.warning("Couldn't trigger training DAG: %s", e)
        
        return f"Promoted to BO{new_version}"
        
    except Exception as e:
        logging.error(f"Promotion failed: {e}")
        raise

def rollback_candidate(**_):
    """Remove latest candidate model artifacts"""
    try:
        # Get latest candidate version
        cand_version, cand_prefix = get_latest_model_version('CO')
        
        s3 = boto3.resource("s3")
        bucket = s3.Bucket(BUCKET)
        
        # Delete candidate objects
        deleted_count = 0
        for obj in bucket.objects.filter(Prefix=cand_prefix):
            obj.delete()
            logging.info("Deleted %s", obj.key)
            deleted_count += 1
        
        logging.info(f"Rolled back candidate CO{cand_version} ({deleted_count} objects deleted)")
        
        # Also trigger training DAG so that a fresh candidate can be retrained
        from airflow.api.common.experimental.trigger_dag import trigger_dag
        try:
            trigger_dag("bangalore_home_prices_pipeline", run_id=f"trigger_after_rollback_{datetime.utcnow().isoformat()}")
        except Exception as e:
            logging.warning("Couldn't trigger training DAG: %s", e)
        
        return f"Rolled back CO{cand_version}"
        
    except Exception as e:
        logging.error(f"Rollback failed: {e}")
        raise

decision = PythonOperator(
    task_id="decide",
    python_callable=decide_promotion,
    dag=dag,
)

promote = PythonOperator(
    task_id="promote",
    python_callable=promote_model,
    dag=dag,
    trigger_rule="all_success",
)

rollback = PythonOperator(
    task_id="rollback",
    python_callable=rollback_candidate,
    dag=dag,
    trigger_rule="all_success",
)

decision >> promote
decision >> rollback
