import pandas as pd
import os
import joblib
from sqlalchemy import create_engine, text
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

# Database configuration
DB_URL = os.getenv("FOREX_DATABASE_URL", "postgresql://forex:forexpass@forexdb:5432/forexdb")
engine = create_engine(DB_URL)

# Ścieżki zapisu pakietów używanych przez live_predictor
PACKAGE_PATH_EUR = os.path.join('models', 'live_package_eurpln.joblib')
PACKAGE_PATH_PLN = os.path.join('models', 'live_package_plneur.joblib')

def train_and_evaluate(series, name):
    """
    Train several candidate models for the given series, select the best one and return it.
    """
    print(f"\n--- Trenowanie dla: {name} ---")
    
    # 1. Feature engineering
    df_temp = pd.DataFrame({name: series})
    # We use 10 lags to match the feature format expected by live_predictor
    for i in range(1, 11):
        df_temp[f'lag_{i}'] = df_temp[name].shift(i)
    df_temp = df_temp.dropna()

    X = df_temp[[f'lag_{i}' for i in range(1, 11)]]
    y = df_temp[name]

    # 2. Train/Test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    # 3. Candidate models to evaluate
    models = {
        "LinearRegression": LinearRegression(),
        "Ridge": Ridge(alpha=1.0),
        "RandomForest": RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
    }

    best_mae = float('inf')
    best_model = None
    best_model_name = ""
    best_r2 = None

    # 4. Training loop
    for m_name, model in models.items():
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        
        mae = mean_absolute_error(y_test, preds)
        r2 = r2_score(y_test, preds)
            try:
                # Fetch data from DB
                print("Fetching data from DB...")
                df = pd.read_sql("SELECT date, eurpln FROM historical_currency ORDER BY date ASC", engine)

                if len(df) < 30:
                    print("Not enough data in DB to train models.")
                    return

                df['plneur'] = 1 / df['eurpln']

                # Train for both directions
                model_eur, name_eur, mae_eur, r2_eur = train_and_evaluate(df['eurpln'], 'eurpln')
                model_pln, name_pln, mae_pln, r2_pln = train_and_evaluate(df['plneur'], 'plneur')

                # Save models to files as packages expected by live_predictor
                os.makedirs('models', exist_ok=True)

                pkg_eur = {
                    "model": model_eur,
                    "meta": {
                        "model_name": name_eur,
                        "mae": float(mae_eur),
                        "r2": float(r2_eur)
                    }
                }

                pkg_pln = {
                    "model": model_pln,
                    "meta": {
                        "model_name": name_pln,
                        "mae": float(mae_pln),
                        "r2": float(r2_pln)
                    }
                }

                # Perform atomic write to the local 'models' folder (used by Airflow and backend)
                tmp_eur = PACKAGE_PATH_EUR + ".tmp"
                tmp_pln = PACKAGE_PATH_PLN + ".tmp"
                joblib.dump(pkg_eur, tmp_eur)
                joblib.dump(pkg_pln, tmp_pln)
                os.replace(tmp_eur, PACKAGE_PATH_EUR)
                os.replace(tmp_pln, PACKAGE_PATH_PLN)

                # Save metrics into the DB table `model_metrics`
                try:
                    with engine.begin() as conn:
                        # We assume the `model_metrics` table was created by Alembic migrations.
                        conn.execute(text("""
                            INSERT INTO model_metrics (pair, selected_model, mae, r2, trained_at)
                            VALUES (:pair, :model, :mae, :r2, NOW())
                        """), {
                            "pair": 'EURPLN',
                            "model": name_eur,
                            "mae": float(mae_eur),
                            "r2": float(r2_eur)
                        })

                        conn.execute(text("""
                            INSERT INTO model_metrics (pair, selected_model, mae, r2, trained_at)
                            VALUES (:pair, :model, :mae, :r2, NOW())
                        """), {
                            "pair": 'PLNEUR',
                            "model": name_pln,
                            "mae": float(mae_pln),
                            "r2": float(r2_pln)
                        })
                except Exception as e:
                    print(f"Error saving metrics to DB: {e}")

            print("\nModel packages saved to 'models/'.")
                print(f"EUR->PLN: {name_eur}")
                print(f"PLN->EUR: {name_pln}")

            except Exception as e:
                print(f"An error occurred: {e}")
                conn.execute(text("""
                    INSERT INTO model_metrics (pair, selected_model, mae, r2, trained_at)
                    VALUES (:pair, :model, :mae, :r2, NOW())
                """), {
                    "pair": 'PLNEUR',
                    "model": name_pln,
                    "mae": float(mae_pln),
                    "r2": float(r2_pln)
                })
        except Exception as e:
            print(f"Error saving metrics to DB: {e}")

    print(f"\nModel packages saved in the 'models' folder.")
        print(f"EUR->PLN: {name_eur}")
        print(f"PLN->EUR: {name_pln}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()