from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from airflow.decorators import dag, task

from fetcher.fetch_rates import fetch_yfinance, upsert_rows, prepare_rows

TICKER_EUR = os.getenv("TICKER_EUR", "EURPLN=X")
TICKER_USD = os.getenv("TICKER_USD", "USDPLN=X")


@dag(
    dag_id="forex_pipeline",
    start_date=datetime(2026, 1, 1),
    schedule="*/30 * * * *",
    catchup=False,
)
def forex_pipeline():

    @task
    def fetch_task(period="1d", interval="15m") -> int:
        eur_df = fetch_yfinance(TICKER_EUR, period=period, interval=interval)
        usd_df = fetch_yfinance(TICKER_USD, period=period, interval=interval)
        rows = prepare_rows(eur_df, usd_df) 
        upsert_rows(rows)
        return len(rows)
    
    @task
    def validate_task() -> None:
        from sql_app.db import DATABASE_URL
        engine = create_engine(DATABASE_URL)
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        with engine.connect() as conn:
            bad = conn.execute(text("""
                SELECT COUNT(*) FROM historical_currency
                WHERE date >= :since AND (
                  (eurpln IS NOT NULL AND eurpln <= 0) OR
                  (usdpln IS NOT NULL AND usdpln <= 0)
                )
            """), {"since": since}).scalar_one()
            if bad > 0:
                raise ValueError(f"Bad rows: {bad}")
            
    @task
    def retention_task() -> int:
        from sql_app.db import DATABASE_URL
        engine = create_engine(DATABASE_URL)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
        with engine.begin() as conn:
            res = conn.execute(text("DELETE FROM historical_currency WHERE date < :cutoff"), {"cutoff": cutoff})
            return res.rowcount

    @task
    def predict_placeholder() -> None:
        print("TODO: prediction step")

    fetch_task() >> validate_task() >> retention_task() >> predict_placeholder()
    

forex_pipeline()