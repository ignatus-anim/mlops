"""Airflow DAG to evaluate A/B prediction logs and promote candidate model."""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import boto3, os, subprocess, logging

DEFAULT_ARGS = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    dag_id="evaluate_ab_dag",
    start_date=datetime(2025, 7, 14),
    schedule_interval="@hourly",
    catchup=False,
    default_args=DEFAULT_ARGS,
)

PG_USER = os.getenv("POSTGRES_USER", "airflow")
PG_PWD = os.getenv("POSTGRES_PASSWORD", "airflow")
PG_HOST = os.getenv("POSTGRES_HOST", "postgres")
PG_DB   = os.getenv("POSTGRES_DB", "airflow")
ENGINE_STR = f"postgresql+psycopg2://{PG_USER}:{PG_PWD}@{PG_HOST}/{PG_DB}"

BUCKET = os.getenv("MLFLOW_S3_BUCKET", "mlops-bucket0982")

CAND_PREFIX = "candidate_model"
PROD_PREFIX = "best_model"

def decide_promotion(**_):
    engine = create_engine(ENGINE_STR)
    with engine.begin() as conn:
        rows = conn.execute(text("""
            SELECT variant, COUNT(*) AS n
            FROM prediction_logs
            WHERE ts > now() - interval '1 day'
            GROUP BY variant
        """)).fetchall()
    counts = {r[0]: r[1] for r in rows}
    cand_n = counts.get(CAND_PREFIX, 0)
    logging.info("Counts 24h: %s", counts)

    # crude rule: promote if candidate served >=100 requests
    if cand_n < 100:
        logging.info("Not enough candidate traffic yet (need 100). Skipping.")
        return "skip"
    return "promote"

def promote_model(**_):
    s3 = boto3.resource("s3")
    bucket = s3.Bucket(BUCKET)

    # copy objects
    for obj in bucket.objects.filter(Prefix=CAND_PREFIX + "/"):
        dest_key = obj.key.replace(CAND_PREFIX, PROD_PREFIX, 1)
        bucket.copy({"Bucket": BUCKET, "Key": obj.key}, dest_key)
        logging.info("Copied %s -> %s", obj.key, dest_key)

    # optionally restart prod container (compose)
    try:
        subprocess.check_call(["docker", "compose", "restart", "infer-prod"])
    except Exception as e:
        logging.warning("Could not restart infer-prod: %s", e)

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

decision >> promote
