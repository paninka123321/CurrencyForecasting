from __future__ import annotations
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, text
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from airflow.decorators import dag, task
from fetcher.fetch_rates import fetch_yfinance, upsert_rows, prepare_rows

TICKER_EUR = os.getenv("TICKER_EUR", "EURPLN=X")
TICKER_USD = os.getenv("TICKER_USD", "USDPLN=X")

@dag(
    dag_id="forex_dual_ml_pipeline",
    start_date=datetime(2026, 1, 1),
    schedule="*/30 * * * *",
    catchup=False,
    tags=["ml", "dual_prediction"]
)
def forex_pipeline():

    @task
    def fetch_task(period="2d", interval="15m") -> int:
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
                WHERE date >= :since AND (eurpln <= 0 OR usdpln <= 0)
            """), {"since": since}).scalar_one()
            if bad > 0:
                raise ValueError(f"Błędne dane w bazie: {bad}")
            
    @task
    def retention_task() -> int:
        from sql_app.db import DATABASE_URL
        engine = create_engine(DATABASE_URL)
        cutoff = datetime.now(timezone.utc) - timedelta(days=2) # Zostawiamy 2 dni dla ML
        with engine.begin() as conn:
            res = conn.execute(text("DELETE FROM historical_currency WHERE date < :cutoff"), {"cutoff": cutoff})
            return res.rowcount

    @task
    def ml_forecast_task() -> str:
        from sql_app.db import DATABASE_URL
        engine = create_engine(DATABASE_URL)
        
        # 1. Pobranie i przygotowanie danych
        df = pd.read_sql("SELECT date, eurpln FROM historical_currency ORDER BY date ASC", engine)
        if len(df) < 20:
            return "Zbyt mało danych"

        df['plneur'] = 1 / df['eurpln']
        
        # 2. Funkcja pomocnicza do trenowania i przewidywania
        def get_prediction(series, name):
            # Tworzenie lagów
            temp_df = pd.DataFrame({name: series})
            for i in range(1, 4):
                temp_df[f'lag_{i}'] = temp_df[name].shift(i)

            temp_df = temp_df.dropna()
            X = temp_df[['lag_1', 'lag_2', 'lag_3']]
            y = temp_df[name]

            # Trening
            model = LinearRegression().fit(X, y)

            # Ocena na zbiorze treningowym (szybka metryka)
            preds_train = model.predict(X)
            mae = float(mean_absolute_error(y, preds_train))
            r2 = float(r2_score(y, preds_train))

            # Predykcja na podstawie ostatnich 3 znanych wartości
            last_values = series.iloc[-3:].values[::-1].reshape(1, -1)
            prediction = float(model.predict(last_values)[0])

            model_version = "linear_lag3_v1"
            return prediction, mae, r2, model_version

        # 3. Wykonanie dwóch niezależnych predykcji
    pred_eurpln, mae_eur, r2_eur, ver_eur = get_prediction(df['eurpln'], 'eurpln')
    pred_plneur, mae_pln, r2_pln, ver_pln = get_prediction(df['plneur'], 'plneur')
        
        next_date = df['date'].iloc[-1] + timedelta(minutes=15)
        
        # 4. Zapis do bazy
        with engine.begin() as conn:
            # Tabela z prognozami (dla kompatybilności z poprzednimi modułami)
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS currency_forecast (
                    date TIMESTAMP PRIMARY KEY,
                    eurpln_pred NUMERIC(18,8),
                    plneur_pred NUMERIC(18,8),
                    model_version VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))

            conn.execute(text("""
                INSERT INTO currency_forecast (date, eurpln_pred, plneur_pred, model_version)
                VALUES (:date, :eur, :pln, :ver)
                ON CONFLICT (date) DO UPDATE SET 
                    eurpln_pred = EXCLUDED.eurpln_pred,
                    plneur_pred = EXCLUDED.plneur_pred
            """), {
                "date": next_date, 
                "eur": pred_eurpln, 
                "pln": pred_plneur, 
                "ver": "dual_linear_v1"
            })

            # Tabela z metrykami modeli (jeśli nie istnieje)
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS model_metrics (
                    id SERIAL PRIMARY KEY,
                    pair VARCHAR(20),
                    selected_model VARCHAR(100),
                    mae NUMERIC(18,8),
                    r2 NUMERIC(18,8),
                    trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))

            # Zapis metryk dla EURPLN
            conn.execute(text("""
                INSERT INTO model_metrics (pair, selected_model, mae, r2, trained_at)
                VALUES (:pair, :model, :mae, :r2, NOW())
            """), {
                "pair": 'EURPLN',
                "model": ver_eur,
                "mae": mae_eur,
                "r2": r2_eur
            })

            # Zapis metryk dla PLNEUR
            conn.execute(text("""
                INSERT INTO model_metrics (pair, selected_model, mae, r2, trained_at)
                VALUES (:pair, :model, :mae, :r2, NOW())
            """), {
                "pair": 'PLNEUR',
                "model": ver_pln,
                "mae": mae_pln,
                "r2": r2_pln
            })
        
        return f"Prognoza na {next_date}: EURPLN={pred_eurpln:.4f}, PLNEUR={pred_plneur:.4f}"

    fetch_task() >> validate_task() >> retention_task() >> ml_forecast_task()

forex_pipeline()