import pandas as pd
from sqlalchemy import create_engine
from sklearn.linear_model import LinearRegression
import joblib
import os

DB_URL = os.getenv("FOREX_DATABASE_URL", "postgresql://postgres:password@db:5432/postgres")
engine = create_engine(DB_URL)

def train_dual_models():
    # Pobranie danych
    df = pd.read_sql("SELECT date, eurpln FROM historical_currency ORDER BY date ASC", engine)
    
    # Tworzymy drugą kolumnę (PLN -> EUR)
    df['plneur'] = 1 / df['eurpln']
    
    # Przygotowanie cech (lags) dla obu kursów
    for i in range(1, 4):
        df[f'eurpln_lag_{i}'] = df['eurpln'].shift(i)
        df[f'plneur_lag_{i}'] = df['plneur'].shift(i)
    
    df = df.dropna()
    
    # --- MODEL 1: EUR -> PLN ---
    X_eur = df[['eurpln_lag_1', 'eurpln_lag_2', 'eurpln_lag_3']]
    y_eur = df['eurpln']
    model_eur = LinearRegression().fit(X_eur, y_eur)
    
    # --- MODEL 2: PLN -> EUR ---
    X_pln = df[['plneur_lag_1', 'plneur_lag_2', 'plneur_lag_3']]
    y_pln = df['plneur']
    model_pln = LinearRegression().fit(X_pln, y_pln)
    
    # Zapis modeli
    os.makedirs('models', exist_ok=True)
    joblib.dump(model_eur, 'models/eurpln_model.joblib')
    joblib.dump(model_pln, 'models/plneur_model.joblib')
    print("Oba modele zostały wytrenowane i zapisane oddzielnie.")

if __name__ == "__main__":
    train_dual_models()