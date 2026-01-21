import pandas as pd
import os
import joblib
from sqlalchemy import create_engine
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

# Konfiguracja bazy
DB_URL = os.getenv("FOREX_DATABASE_URL", "postgresql://forex:forexpass@forexdb:5432/forexdb")
engine = create_engine(DB_URL)

def train_and_evaluate(series, name):
    """
    Trenuje kilka modeli dla danej serii, wybiera najlepszy i zwraca go.
    """
    print(f"\n--- Trenowanie dla: {name} ---")
    
    # 1. Feature Engineering
    df_temp = pd.DataFrame({name: series})
    for i in range(1, 4):
        df_temp[f'lag_{i}'] = df_temp[name].shift(i)
    df_temp = df_temp.dropna()

    X = df_temp[['lag_1', 'lag_2', 'lag_3']]
    y = df_temp[name]

    # 2. Podział Train/Test
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    # 3. Lista modeli do sprawdzenia
    models = {
        "LinearRegression": LinearRegression(),
        "Ridge": Ridge(alpha=1.0),
        "RandomForest": RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
    }

    best_mae = float('inf')
    best_model = None
    best_model_name = ""

    # 4. Pętla treningowa
    for m_name, model in models.items():
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        
        mae = mean_absolute_error(y_test, preds)
        r2 = r2_score(y_test, preds)
        
        print(f"Model: {m_name:20} | MAE: {mae:.6f} | R2: {r2:.4f}")
        
        if mae < best_mae:
            best_mae = mae
            best_model = model
            best_model_name = m_name

    print(f" >>> ZWYCIĘZCA dla {name}: {best_model_name} (MAE: {best_mae:.6f})")
    
    # Opcjonalnie: Dotrenowanie zwycięzcy na pełnych danych przed zapisem
    best_model.fit(X, y)
    
    return best_model, best_model_name

def main():
    try:
        # Pobranie danych
        print("Pobieranie danych z bazy...")
        df = pd.read_sql("SELECT date, eurpln FROM historical_currency ORDER BY date ASC", engine)
        
        if len(df) < 30:
            print("Zbyt mało danych w bazie, by trenować modele.")
            return

        df['plneur'] = 1 / df['eurpln']
        
        # Trening dla obu kierunków
        model_eur, name_eur = train_and_evaluate(df['eurpln'], 'eurpln')
        model_pln, name_pln = train_and_evaluate(df['plneur'], 'plneur')

        # Zapis modeli do plików
        os.makedirs('models', exist_ok=True)
        joblib.dump(model_eur, 'models/best_eurpln_model.joblib')
        joblib.dump(model_pln, 'models/best_plneur_model.joblib')
        
        print(f"\nModele zapisane w folderze 'models/'.")
        print(f"EUR->PLN: {name_eur}")
        print(f"PLN->EUR: {name_pln}")

    except Exception as e:
        print(f"Wystąpił błąd: {e}")

if __name__ == "__main__":
    main()