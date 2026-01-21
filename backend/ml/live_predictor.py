import time
import joblib
import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta # <--- Dodane timedelta
from sqlalchemy import create_engine, text

# Konfiguracja
PATH_EUR = "/app/models/live_package_eurpln.joblib"
PATH_PLN = "/app/models/live_package_plneur.joblib"
DB_URL = os.getenv("FOREX_DATABASE_URL", "postgresql://postgres:password@db:5432/postgres")
TICKER = "EURPLN=X"

def init_tables(engine):
    """Tworzy tabele z jasnym podziałem na czas wykonania i czas prognozy"""
    with engine.begin() as conn:
        # Tabela 1: EUR -> PLN
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS predictions_eurpln (
                target_date TIMESTAMP PRIMARY KEY,  -- NA KIEDY jest prognoza (Oś X na wykresie)
                execution_date TIMESTAMP,           -- KIEDY model to policzył
                predicted_rate NUMERIC(18, 8),
                model_name VARCHAR(50),
                mae NUMERIC(18, 8),
                r2 NUMERIC(18, 8)
            )
        """))
        # Tabela 2: PLN -> EUR
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS predictions_plneur (
                target_date TIMESTAMP PRIMARY KEY,  -- NA KIEDY jest prognoza
                execution_date TIMESTAMP,           -- KIEDY model to policzył
                predicted_rate NUMERIC(18, 8),
                model_name VARCHAR(50),
                mae NUMERIC(18, 8),
                r2 NUMERIC(18, 8)
            )
        """))

def run_live_loop():
    engine = create_engine(DB_URL)
    init_tables(engine)
    
    pkg_eur = None
    pkg_pln = None
    last_load_time = 0
    
    price_buffer_eur = []

    print("--- START DUAL PREDICTOR (Target Date Corrected) ---")

    while True:
        try:
            loop_start = time.time()

            # 1. Sprawdź i załaduj modele
            if os.path.exists(PATH_EUR) and os.path.exists(PATH_PLN):
                mod_time = os.path.getmtime(PATH_EUR)
                if mod_time > last_load_time:
                    print(f"[{datetime.now().time()}] Przeładowanie modeli...")
                    try:
                        pkg_eur = joblib.load(PATH_EUR)
                        pkg_pln = joblib.load(PATH_PLN)
                        last_load_time = mod_time
                    except Exception as e:
                        print(f"Błąd ładowania: {e}")

            if pkg_eur is None or pkg_pln is None:
                print("Czekam na modele z Airflow...")
                time.sleep(10)
                continue

            # 2. Pobierz dane
            df = yf.download(TICKER, period="1d", interval="1m", progress=False)
            
            if not df.empty:
                curr_eur = float(df['Close'].iloc[-1])
                
                price_buffer_eur.append(curr_eur)
                if len(price_buffer_eur) > 10:
                    price_buffer_eur.pop(0)

                # 3. Predykcja
                if len(price_buffer_eur) == 10:
                    # Obliczamy czasy
                    now = datetime.now()
                    target_time = now + timedelta(minutes=1) # <--- KLUCZOWA ZMIANA
                    
                    # --- EUR -> PLN ---
                    feats_eur = pd.DataFrame([price_buffer_eur[::-1]], columns=[f'lag_{i}' for i in range(10)])
                    pred_eur_val = float(pkg_eur["model"].predict(feats_eur)[0])
                    meta_eur = pkg_eur["meta"]

                    # --- PLN -> EUR ---
                    buffer_pln = [1.0/x for x in price_buffer_eur]
                    feats_pln = pd.DataFrame([buffer_pln[::-1]], columns=[f'lag_{i}' for i in range(10)])
                    pred_pln_val = float(pkg_pln["model"].predict(feats_pln)[0])
                    meta_pln = pkg_pln["meta"]

                    print(f"[{now.strftime('%H:%M')}] Cel: {target_time.strftime('%H:%M')} | EUR: {pred_eur_val:.4f} | PLN: {pred_pln_val:.4f}")

                    # 4. Zapis do bazy (Z uwzględnieniem target_date)
                    with engine.begin() as conn:
                        # EURPLN
                        conn.execute(text("""
                            INSERT INTO predictions_eurpln (target_date, execution_date, predicted_rate, model_name, mae, r2)
                            VALUES (:target, :exec, :pred, :model, :mae, :r2)
                            ON CONFLICT (target_date) DO UPDATE SET predicted_rate = EXCLUDED.predicted_rate
                        """), {
                            "target": target_time, 
                            "exec": now,
                            "pred": pred_eur_val, 
                            "model": meta_eur['model_name'], 
                            "mae": meta_eur['mae'], 
                            "r2": meta_eur['r2']
                        })

                        # PLNEUR
                        conn.execute(text("""
                            INSERT INTO predictions_plneur (target_date, execution_date, predicted_rate, model_name, mae, r2)
                            VALUES (:target, :exec, :pred, :model, :mae, :r2)
                            ON CONFLICT (target_date) DO UPDATE SET predicted_rate = EXCLUDED.predicted_rate
                        """), {
                            "target": target_time, 
                            "exec": now,
                            "pred": pred_pln_val, 
                            "model": meta_pln['model_name'], 
                            "mae": meta_pln['mae'], 
                            "r2": meta_pln['r2']
                        })

            elapsed = time.time() - loop_start
            sleep_time = max(0, 60 - elapsed)
            time.sleep(sleep_time)

        except Exception as e:
            print(f"Błąd w pętli: {e}")
            time.sleep(30)

if __name__ == "__main__":
    run_live_loop()