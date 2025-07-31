"""Utility to log inference requests to Postgres.
Creates table `prediction_logs` on startup if missing.
"""
import os
import json
import datetime as dt
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from pathlib import Path

# Connection string from env or default (same postgres service)
PG_USER = os.getenv("POSTGRES_USER", "airflow")
PG_PWD = os.getenv("POSTGRES_PASSWORD", "airflow")
PG_HOST = os.getenv("POSTGRES_HOST", "postgres")
PG_DB   = os.getenv("POSTGRES_DB", "airflow")

# Build connection string so it can be reused by other modules
ENGINE_STR = f"postgresql+psycopg2://{PG_USER}:{PG_PWD}@{PG_HOST}/{PG_DB}"

# Create SQLAlchemy engine
ENGINE = create_engine(ENGINE_STR)

# JSON logging setup
LOG_DIR = Path("/app/logs")
LOG_DIR.mkdir(exist_ok=True)
PREDICTION_LOG_FILE = LOG_DIR / "predictions.jsonl"
FEEDBACK_LOG_FILE = LOG_DIR / "feedback.jsonl"

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS prediction_logs (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMP WITH TIME ZONE NOT NULL,
    variant TEXT NOT NULL,
    location TEXT,
    sqft DOUBLE PRECISION,
    bhk INTEGER,
    bath INTEGER,
    prediction DOUBLE PRECISION,
    prediction_time_ms DOUBLE PRECISION,  -- Model inference time in milliseconds
    session_id TEXT,  -- Track user sessions
    user_ip TEXT      -- For basic user identification
);

CREATE TABLE IF NOT EXISTS user_feedback (
    id SERIAL PRIMARY KEY,
    prediction_id INTEGER REFERENCES prediction_logs(id),
    feedback_type TEXT NOT NULL,  -- 'rating', 'too_high', 'too_low', 'accurate'
    feedback_value DOUBLE PRECISION,  -- 1-5 rating or actual price if provided
    feedback_text TEXT,  -- Optional comment
    feedback_ts TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    user_ip TEXT
);

CREATE TABLE IF NOT EXISTS feature_logs (
    id SERIAL PRIMARY KEY,
    prediction_id INTEGER REFERENCES prediction_logs(id),
    features JSONB NOT NULL,
    ts TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prediction_logs_variant_ts ON prediction_logs(variant, ts);
CREATE INDEX IF NOT EXISTS idx_user_feedback_prediction_id ON user_feedback(prediction_id);
CREATE INDEX IF NOT EXISTS idx_feature_logs_prediction_id ON feature_logs(prediction_id);
CREATE INDEX IF NOT EXISTS idx_feature_logs_ts ON feature_logs(ts);
"""

with ENGINE.begin() as conn:
    conn.execute(text(TABLE_SQL))

@contextmanager
def get_conn():
    with ENGINE.begin() as conn:
        yield conn

def log_to_json_file(filename: Path, data: dict):
    """Append JSON record to log file"""
    try:
        with open(filename, 'a') as f:
            f.write(json.dumps(data, default=str) + '\n')
    except Exception as e:
        print(f"Failed to write to JSON log {filename}: {e}")

def log_request(variant: str, location: str, sqft: float, bhk: int, bath: int, prediction: float, prediction_time_ms: float, session_id: str = None, user_ip: str = None):
    """Insert a single log row and return the prediction ID."""
    timestamp = dt.datetime.utcnow()
    
    # Prepare data for both DB and JSON logging
    log_data = {
        "ts": timestamp,
        "variant": variant,
        "location": location,
        "sqft": sqft,
        "bhk": bhk,
        "bath": bath,
        "prediction": prediction,
        "prediction_time_ms": prediction_time_ms,
        "session_id": session_id,
        "user_ip": user_ip,
    }
    
    prediction_id = None
    
    # Log to PostgreSQL
    try:
        with get_conn() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO prediction_logs (ts, variant, location, sqft, bhk, bath, prediction, prediction_time_ms, session_id, user_ip)
                    VALUES (:ts, :variant, :loc, :sqft, :bhk, :bath, :pred, :prediction_time_ms, :session_id, :user_ip)
                    RETURNING id
                """),
                {
                    "ts": timestamp,
                    "variant": variant,
                    "loc": location,
                    "sqft": sqft,
                    "bhk": bhk,
                    "bath": bath,
                    "pred": prediction,
                    "prediction_time_ms": prediction_time_ms,
                    "session_id": session_id,
                    "user_ip": user_ip,
                },
            )
            prediction_id = result.fetchone()[0]
            log_data["prediction_id"] = prediction_id
            
            # Log features for drift detection
            features = {
                'total_sqft': float(sqft),
                'bhk': int(bhk),
                'bath': int(bath),
                'location': location,
                'prediction': float(prediction)
            }
            
            conn.execute(
                text("""
                    INSERT INTO feature_logs (prediction_id, features, ts)
                    VALUES (:prediction_id, :features, :ts)
                """),
                {
                    "prediction_id": prediction_id,
                    "features": json.dumps(features),
                    "ts": timestamp
                }
            )
    except Exception as e:
        print(f"Failed to log to PostgreSQL: {e}")
        # Still try to log to JSON even if DB fails
        log_data["db_error"] = str(e)
    
    # Log to JSON file (always, as backup)
    log_to_json_file(PREDICTION_LOG_FILE, log_data)
    
    return prediction_id

def log_feedback(prediction_id: int, feedback_type: str, feedback_value: float = None, feedback_text: str = None, user_ip: str = None):
    """Log user feedback for a prediction."""
    timestamp = dt.datetime.utcnow()
    
    # Prepare data for both DB and JSON logging
    feedback_data = {
        "ts": timestamp,
        "prediction_id": prediction_id,
        "feedback_type": feedback_type,
        "feedback_value": feedback_value,
        "feedback_text": feedback_text,
        "user_ip": user_ip,
    }
    
    # Log to PostgreSQL
    try:
        with get_conn() as conn:
            conn.execute(
                text("""
                    INSERT INTO user_feedback (prediction_id, feedback_type, feedback_value, feedback_text, user_ip)
                    VALUES (:pred_id, :fb_type, :fb_value, :fb_text, :user_ip)
                """),
                {
                    "pred_id": prediction_id,
                    "fb_type": feedback_type,
                    "fb_value": feedback_value,
                    "fb_text": feedback_text,
                    "user_ip": user_ip,
                },
            )
    except Exception as e:
        print(f"Failed to log feedback to PostgreSQL: {e}")
        feedback_data["db_error"] = str(e)
    
    # Log to JSON file (always, as backup)
    log_to_json_file(FEEDBACK_LOG_FILE, feedback_data)
