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

def get_features(df_input):
    df = df_input.copy()
    df['Log_Ret'] = np.log(df['Close'] / df['Close'].shift(1))
    # Momentum (3h)
    df['Mom'] = df['Close'].diff(3)
    # Volatity (12h)
    df['Volat'] = df['Log_Ret'].rolling(12).std()
    # RSI (Relative Strength Index)
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

    def load_all_models(prefix):
        models = {"XGB": [], "Ridge": []}
        scaler_path = os.path.join(MODEL_DIR, f"scaler_{prefix.lower()}.joblib")
        
        if not os.path.exists(scaler_path):
            raise FileNotFoundError(f"Nie znaleziono skalera w {scaler_path}")
            
        scaler = joblib.load(scaler_path)
        
        for s in SEEDS:
            # Loading Ridge i XGB
            ridge_path = os.path.join(MODEL_DIR, f"{prefix.lower()}_ridge_s{s}.joblib")
            xgb_path = os.path.join(MODEL_DIR, f"{prefix.lower()}_xgb_s{s}.joblib")
            
            if os.path.exists(ridge_path):
                models["Ridge"].append(joblib.load(ridge_path))
            if os.path.exists(xgb_path):
                models["XGB"].append(joblib.load(xgb_path))
                
        return models, scaler

    # 1. Get data
    full_data = yf.download(f"{TICKER_TO_LOAD}=X", period="5d", interval="1h", progress=False, auto_adjust=True)
    df_active = get_features(full_data)
    loaded_models, active_scaler = load_all_models(TICKER_TO_LOAD)

    # 3. Lookback
    end_idx = len(df_active)
    start_idx = end_idx - LOOKBACK
    last_p = df_active['Close'].values[end_idx - 1]

    # 4. Time (warsaw)
    if df_active.index.tz is None:
        history_dates = df_active.index[start_idx:end_idx].tz_localize('UTC').tz_convert('Europe/Warsaw')
    else:
        history_dates = df_active.index[start_idx:end_idx].tz_convert('Europe/Warsaw')

    last_ts = history_dates[-1]
    forecast_dates = pd.date_range(start=last_ts, periods=FORECAST + 1, freq='h')
    x_raw = df_active[['Log_Ret', 'RSI', 'Mom', 'Volat']].values[start_idx:end_idx]
    x_s = active_scaler.transform(x_raw).reshape(1, -1) 

    # 6. Pred
    raw_results = {"XGB": [], "Ridge": []}
    for m in loaded_models["Ridge"]:
        raw_results["Ridge"].append(m.predict(x_s).flatten())
    for m in loaded_models["XGB"]:
        raw_results["XGB"].append(m.predict(x_s).flatten())

    # plot
    plt.style.use('ggplot') 
    fig, ax = plt.subplots(figsize=(12, 6), facecolor='white')

    ax.plot(history_dates, df_active['Close'].values[start_idx:end_idx], 
            label="History (Last 24h)", color='#2c3e50', linewidth=2)
    ax.axvline(x=last_ts, color='#e74c3c', linestyle='--', alpha=0.6, label="Prediction Start")
    colors = {"XGB": "#2ecc71", "Ridge": "#3498db"}
    
    for name, col in colors.items():
        if not raw_results[name]: continue
        
        preds = last_p + np.array(raw_results[name])
        avg_p = np.insert(np.mean(preds, axis=0), 0, last_p)
        min_p = np.insert(np.min(preds, axis=0), 0, last_p)
        max_p = np.insert(np.max(preds, axis=0), 0, last_p)
        
        ax.plot(forecast_dates, avg_p, color=col, marker='o', label=f"{name} Forecast", linewidth=2)
        ax.fill_between(forecast_dates, min_p, max_p, color=col, alpha=0.15)

    ax.set_title(f"{TICKER_TO_LOAD} 4 hour forecast", fontsize=14, fontweight='bold')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xticks(rotation=45)
    plt.legend(loc='upper left')
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    plt.close(fig)
    buf.seek(0)
    
    return base64.b64encode(buf.read()).decode('utf-8')