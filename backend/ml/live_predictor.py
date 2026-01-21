import time
import joblib
import os
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta # <--- Dodane timedelta
from sqlalchemy import create_engine, text

# Konfiguracja
PATH_EUR = "/app/models/live_package_eurpln.joblib"
PATH_PLN = "/app/models/live_package_plneur.joblib"
DB_URL = os.getenv("FOREX_DATABASE_URL", "postgresql://forex:forexpass@forexdb:5432/forexdb")
TICKER = "EURPLN=X"

def init_tables(engine):
    """Verify that the tables required by the predictor exist.

    Note: this function does not create tables — we assume Alembic migrations
    (or the ops team) have provisioned them. If missing, a warning is logged.
    """
    required = ['predictions_eurpln', 'predictions_plneur']
    with engine.connect() as conn:
        for table in required:
            # Sprawdzamy istnienie tabeli; nie tworzymy jej tutaj.
            res = conn.execute(text("SELECT to_regclass(:t)"), {"t": f"public.{table}"}).scalar()
            if not res:
                print(f"WARNING: tabela '{table}' nie istnieje. Upewnij się, że migracje zostały zastosowane.")

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

            # 1. Check and load models
            if os.path.exists(PATH_EUR) and os.path.exists(PATH_PLN):
                mod_time = os.path.getmtime(PATH_EUR)
                if mod_time > last_load_time:
                    print(f"[{datetime.now().time()}] Reloading models...")
                    try:
                        pkg_eur = joblib.load(PATH_EUR)
                        pkg_pln = joblib.load(PATH_PLN)
                        last_load_time = mod_time
                        # debug: wypisz podstawowe info o załadowanych pakietach
                        try:
                            print('MODEL LOAD DEBUG: pkg_eur keys=', list(pkg_eur.keys()))
                            print('MODEL LOAD DEBUG: pkg_pln keys=', list(pkg_pln.keys()))
                            print('MODEL LOAD DEBUG: eur model type=', type(pkg_eur.get('model')),
                                  'meta sample=', {k: pkg_eur.get('meta', {}).get(k) for k in ('model_name','mae','r2')})
                            print('MODEL LOAD DEBUG: pln model type=', type(pkg_pln.get('model')),
                                  'meta sample=', {k: pkg_pln.get('meta', {}).get(k) for k in ('model_name','mae','r2')})
                        except Exception as e:
                            print('MODEL LOAD DEBUG ERROR:', e)
                    except Exception as e:
                        print(f"Load error: {e}")

            if pkg_eur is None or pkg_pln is None:
                print("Waiting for models from Airflow...")
                time.sleep(10)
                continue

            # 2. Fetch data
            df = yf.download(TICKER, period="1d", interval="1m", progress=False)
            
            if not df.empty:
                # df['Close'].iloc[-1] can sometimes be a Series (depending on yfinance return shape)
                # normalize to a scalar safely
                last_close = df['Close'].iloc[-1]
                try:
                    if isinstance(last_close, (pd.Series,)):
                        curr_eur = float(last_close.values.ravel()[-1])
                    else:
                        curr_eur = float(last_close)
                except Exception as e:
                    # fallback using numpy coercion
                    import numpy as _np
                    arr = _np.asarray(last_close)
                    curr_eur = float(arr.ravel()[-1])
                print('DEBUG: current eur close extracted=', curr_eur)
                
                price_buffer_eur.append(curr_eur)
                if len(price_buffer_eur) > 10:
                    price_buffer_eur.pop(0)

                # 3. Prediction
                if len(price_buffer_eur) == 10:
                    # Obliczamy czasy
                    now = datetime.now()
                    target_time = now + timedelta(minutes=1) # <--- KLUCZOWA ZMIANA
                    
                    try:
                        # --- EUR -> PLN ---
                        feats_eur = pd.DataFrame([price_buffer_eur[::-1]], columns=[f'lag_{i}' for i in range(1, 11)])
                        pred_raw_eur = pkg_eur["model"].predict(feats_eur)
                        # Normalize prediction output to a scalar safely
                        try:
                            pred_arr = np.asarray(pred_raw_eur)
                            pred_eur_val = float(pred_arr.ravel()[0])
                        except Exception:
                            # fallback to direct float cast if possible
                            pred_eur_val = float(pred_raw_eur[0])
                        meta_eur = pkg_eur["meta"]

                        # --- PLN -> EUR ---
                        buffer_pln = [1.0/x for x in price_buffer_eur]
                        feats_pln = pd.DataFrame([buffer_pln[::-1]], columns=[f'lag_{i}' for i in range(1, 11)])
                        pred_raw_pln = pkg_pln["model"].predict(feats_pln)
                        try:
                            pred_arr_pln = np.asarray(pred_raw_pln)
                            pred_pln_val = float(pred_arr_pln.ravel()[0])
                        except Exception:
                            pred_pln_val = float(pred_raw_pln[0])
                        meta_pln = pkg_pln["meta"]
                    except Exception as e:
                        print("Prediction error:", e)
                        try:
                            print("feats_eur:", feats_eur)
                        except Exception:
                            pass
                        try:
                            print('pred_raw_eur type:', type(pred_raw_eur), 'value:', pred_raw_eur)
                        except Exception:
                            pass
                        try:
                            print('pkg_eur model type:', type(pkg_eur.get('model')))
                        except Exception:
                            pass
                        # skip this iteration
                        time.sleep(60)
                        continue

                    print(f"[{now.strftime('%H:%M')}] Target: {target_time.strftime('%H:%M')} | EUR: {pred_eur_val:.4f} | PLN: {pred_pln_val:.4f}")

                        # 4. Write to DB (including target_date)
                    with engine.begin() as conn:
                        # EURPLN
                        try:
                            print('DEBUG: types before insert ->',
                                  type(pred_eur_val), type(meta_eur.get('mae')), type(meta_eur.get('r2')))
                            print('DEBUG: types PLN ->', type(pred_pln_val), type(meta_pln.get('mae')), type(meta_pln.get('r2')))

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
                        except Exception as e:
                            import traceback
                            print('DB insert error:', e)
                            print(traceback.format_exc())
                            # continue main loop

            elapsed = time.time() - loop_start
            sleep_time = max(0, 60 - elapsed)
            time.sleep(sleep_time)

        except Exception as e:
            import traceback
            print(f"Loop error: {e}")
            print('FULL TRACEBACK:')
            print(traceback.format_exc())
            # small sleep to avoid tight error loop
            time.sleep(30)

if __name__ == "__main__":
    run_live_loop()