"""Utility to log inference requests to Postgres.
Creates table `prediction_logs` on startup if missing.
"""
import os
import datetime as dt
from contextlib import contextmanager
from sqlalchemy import create_engine, text

# Connection string from env or default (same postgres service)
PG_USER = os.getenv("POSTGRES_USER", "airflow")
PG_PWD = os.getenv("POSTGRES_PASSWORD", "airflow")
PG_HOST = os.getenv("POSTGRES_HOST", "postgres")
PG_DB   = os.getenv("POSTGRES_DB", "airflow")

ENGINE = create_engine(f"postgresql+psycopg2://{PG_USER}:{PG_PWD}@{PG_HOST}/{PG_DB}")

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS prediction_logs (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMP WITH TIME ZONE NOT NULL,
    variant TEXT NOT NULL,
    location TEXT,
    sqft DOUBLE PRECISION,
    bhk INTEGER,
    bath INTEGER,
    prediction DOUBLE PRECISION
);
"""

with ENGINE.begin() as conn:
    conn.execute(text(TABLE_SQL))

@contextmanager
def get_conn():
    with ENGINE.begin() as conn:
        yield conn

def log_request(variant: str, location: str, sqft: float, bhk: int, bath: int, prediction: float):
    """Insert a single log row."""
    with get_conn() as conn:
        conn.execute(
            text("""
                INSERT INTO prediction_logs (ts, variant, location, sqft, bhk, bath, prediction)
                VALUES (:ts, :variant, :loc, :sqft, :bhk, :bath, :pred)
            """),
            {
                "ts": dt.datetime.utcnow(),
                "variant": variant,
                "loc": location,
                "sqft": sqft,
                "bhk": bhk,
                "bath": bath,
                "pred": prediction,
            },
        )
