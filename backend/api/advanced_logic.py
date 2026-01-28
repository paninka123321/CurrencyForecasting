import io
import base64
import os
import joblib
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from datetime import datetime, timedelta
import pytz

def get_features(df_input):
    df = df_input.copy()
    df['Log_Ret'] = np.log(df['Close'] / df['Close'].shift(1))
    df['Mom'] = df['Close'].diff(3)
    df['Volat'] = df['Log_Ret'].rolling(12).std()
    diff = df['Close'].diff()
    up = diff.clip(lower=0).rolling(14).mean()
    down = -diff.clip(upper=0).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (up / down)))
    return df.dropna()

def generate_advanced_plot(ticker):
    TICKER_TO_LOAD = ticker 
    BASE_API_DIR = Path(__file__).resolve().parent
    MODEL_DIR = os.path.join(BASE_API_DIR, "advanced_models")
    SEEDS = [42, 21]
    LOOKBACK, FORECAST = 24, 4
    WARSAW_TZ = pytz.timezone('Europe/Warsaw')

    def load_all_models(prefix):
        models = {"XGB": [], "Ridge": []}
        scaler_path = os.path.join(MODEL_DIR, f"scaler_{prefix.lower()}.joblib")
        if not os.path.exists(scaler_path):
            raise FileNotFoundError(f"Nie znaleziono skalera w {scaler_path}")
        scaler = joblib.load(scaler_path)
        for s in SEEDS:
            ridge_path = os.path.join(MODEL_DIR, f"{prefix.lower()}_ridge_s{s}.joblib")
            xgb_path = os.path.join(MODEL_DIR, f"{prefix.lower()}_xgb_s{s}.joblib")
            if os.path.exists(ridge_path):
                models["Ridge"].append(joblib.load(ridge_path))
            if os.path.exists(xgb_path):
                models["XGB"].append(joblib.load(xgb_path))
        return models, scaler

    # 1. Pobieranie danych
    full_data = yf.download(f"{TICKER_TO_LOAD}=X", period="5d", interval="1h", progress=False, auto_adjust=True)
    
    if full_data.index.tz is None:
        full_data.index = full_data.index.tz_localize('UTC')
    full_data.index = full_data.index.tz_convert(WARSAW_TZ)

    df_active = get_features(full_data)
    loaded_models, active_scaler = load_all_models(TICKER_TO_LOAD)

    # 3. Wyodrębnienie okna
    df_recent = df_active.tail(LOOKBACK)
    last_p = float(np.ravel(df_recent['Close'])[-1])
    
    # --- KLUCZOWA POPRAWKA: CZAS DLA MATPLOTLIB ---
    # Konwertujemy na czas "naiwny" (usuwamy info o strefie, zostawiając same godziny warszawskie)
    # To wymusza na Matplotlib pokazywanie dokładnie tych godzin, które są w danych.
    history_dates_plot = df_recent.index.tz_localize(None)
    last_ts_plot = history_dates_plot[-1]
    forecast_dates_plot = pd.date_range(start=last_ts_plot, periods=FORECAST + 1, freq='h')

    # 4. Przygotowanie wejścia (używamy oryginalnych danych)
    x_raw = df_recent[['Log_Ret', 'RSI', 'Mom', 'Volat']].values
    x_s = active_scaler.transform(x_raw).reshape(1, -1) 

    # 5. Predykcja
    raw_results = {"XGB": [], "Ridge": []}
    for m in loaded_models["Ridge"]:
        raw_results["Ridge"].append(m.predict(x_s).flatten())
    for m in loaded_models["XGB"]:
        raw_results["XGB"].append(m.predict(x_s).flatten())

    # 6. Wizualizacja
    plt.style.use('ggplot') 
    fig, ax = plt.subplots(figsize=(12, 6), facecolor='white')

    # Rysujemy historię używając "naiwnych" dat
    ax.plot(history_dates_plot, df_recent['Close'].values.flatten(), 
            label="History (Last 24h)", color='#2c3e50', linewidth=2.5)
    
    # CZERWONA LINIA - startuje w punktach "naiwnych"
    ax.axvline(x=last_ts_plot, color='#e74c3c', linestyle='--', alpha=0.9)
    
    # Napis godziny nad linią
    ax.text(last_ts_plot, ax.get_ylim()[1], f"  {last_ts_plot.strftime('%H:%M')}", 
            color='#e74c3c', verticalalignment='bottom', fontweight='bold', fontsize=10)

    # Kolory dla modeli
    colors = {"XGB": "#2ecc71", "Ridge": "#3498db"}
    for name, col in colors.items():
        if not raw_results[name]: continue
        
        preds_array = np.array(raw_results[name])
        avg_p = np.insert(np.mean(preds_array, axis=0), 0, 0) + last_p
        min_p = np.insert(np.min(preds_array, axis=0), 0, 0) + last_p
        max_p = np.insert(np.max(preds_array, axis=0), 0, 0) + last_p
        
        # Plot prognozy na "naiwnych" datach
        ax.plot(forecast_dates_plot, avg_p, color=col, marker='o', markersize=5, label=f"{name} Forecast", linewidth=2)
        ax.fill_between(forecast_dates_plot, min_p, max_p, color=col, alpha=0.1)

    # Tytuł z czasem systemowym
    current_time_str = datetime.now(WARSAW_TZ).strftime('%H:%M:%S')
    ax.set_title(f"{TICKER_TO_LOAD} 4h Forecast | Current: {current_time_str}", fontsize=14, fontweight='bold')
    
    # Oś X - teraz format '%H:%M' pokaże dokładnie to, co jest w history_dates_plot
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    
    plt.xticks(rotation=45)
    plt.legend(loc='upper left', frameon=True, facecolor='white', framealpha=0.8)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=110)
    plt.close(fig)
    buf.seek(0)
    
    return base64.b64encode(buf.read()).decode('utf-8')