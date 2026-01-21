#!/usr/bin/env python
import os
import argparse
from pathlib import Path
from dotenv import load_dotenv
import yfinance as yf
import pandas as pd
from decimal import Decimal
from sqlalchemy.dialects.postgresql import insert as pg_insert

# Upewnij się, że te importy działają w Twojej strukturze
# Jeśli uruchamiasz to przez Docker, PYTHONPATH powinien to obsłużyć
from sql_app.db import engine
from sql_app.models import historical_currency

# Ładowanie zmiennych środowiskowych
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / '.env')

TICKER_EUR = os.getenv('TICKER_EUR', 'EURPLN=X')
TICKER_USD = os.getenv('TICKER_USD', 'USDPLN=X')

def fetch_yfinance(ticker: str, period: str, interval: str):
    """
    Pobiera dane z Yahoo Finance i czyści strefy czasowe.
    """
    print(f"Fetching {ticker} (period={period}, interval={interval})...")
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=period, interval=interval)
        
        if df.empty:
            print(f"Warning: Empty dataframe for {ticker}")
            return pd.DataFrame()

        # Usunięcie strefy czasowej (konwersja na 'naiwny' UTC),
        # żeby Postgres nie zgłaszał błędów.
        if df.index.tz is not None:
            df.index = df.index.tz_convert('UTC').tz_localize(None)
            
        # Zostawiamy tylko Close i zmieniamy nazwę na ticker
        df = df[['Close']].rename(columns={'Close': ticker})
        return df
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return pd.DataFrame()

def prepare_rows(eur_df, usd_df):
    """
    Łączy dane EUR i USD w jeden format gotowy do wstawienia do bazy.
    """
    if eur_df.empty and usd_df.empty:
        return []

    # Łączymy po indeksie (czasie)
    # axis=1 oznacza, że łączymy kolumny obok siebie dla tych samych dat
    df = pd.concat([eur_df, usd_df], axis=1)
    
    # Usuwamy wiersze, gdzie obie waluty są NaN
    df = df.dropna(how='all')
    
    # Wyciągamy datę z indeksu do kolumny
    df = df.reset_index()
    
    # Upewniamy się, że kolumna z datą nazywa się 'date'
    # (reset_index domyślnie nazywa ją 'Date' lub 'index')
    if 'Date' in df.columns:
        df = df.rename(columns={'Date': 'date'})
    elif 'index' in df.columns:
        df = df.rename(columns={'index': 'date'})
        
    # Jeśli nadal nie ma kolumny 'date', bierzemy pierwszą
    if 'date' not in df.columns:
         df = df.rename(columns={df.columns[0]: 'date'})

    rows = []
    for _, r in df.iterrows():
        try:
            # Konwersja daty na pythonowy datetime
            date_val = pd.to_datetime(r['date']).to_pydatetime()

            eurv = r.get(TICKER_EUR)
            usdv = r.get(TICKER_USD)

            # Konwersja na Decimal (bezpieczniej dla walut)
            eur = Decimal(str(eurv)) if pd.notna(eurv) else None
            usd = Decimal(str(usdv)) if pd.notna(usdv) else None
            
            # Dodajemy tylko jeśli mamy datę
            if date_val:
                rows.append({'date': date_val, 'eurpln': eur, 'usdpln': usd})
        except Exception as e:
            print(f"Skipping row due to error: {e}")
            continue
            
    return rows

def upsert_rows(rows):
    """
    Wstawia wiersze do bazy. Jeśli data istnieje -> aktualizuje kursy.
    """
    if not rows:
        print('No rows to insert')
        return

    # Używamy context managera (with engine.begin), który sam robi commit lub rollback
    try:
        with engine.begin() as conn:
            stmt = pg_insert(historical_currency).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=['date'], # Upewnij się, że w modelu 'date' jest Primary Key lub Unique
                set_={'eurpln': stmt.excluded.eurpln, 'usdpln': stmt.excluded.usdpln}
            )
            result = conn.execute(stmt)
            print(f"Upserted {len(rows)} rows.")
    except Exception as e:
        print(f"Database error: {e}")

def parse_args():
    p = argparse.ArgumentParser(description="Fetch FX rates from yfinance and upsert into Postgres.")
    p.add_argument(
        "--period",
        default=os.getenv("YF_PERIOD", "7d"),
        help="yfinance period. Default: 7d",
    )
    p.add_argument(
        "--interval",
        default=os.getenv("YF_INTERVAL", "1h"),
        help="yfinance interval. Default: 1h",
    )
    return p.parse_args()

if __name__ == '__main__':
    # Ta sekcja uruchamia się TYLKO przy ręcznym wywołaniu: python fetch_rates.py
    # DAG importuje funkcje wyżej, więc omija ten blok.
    args = parse_args()

    print(f'--- Manual Fetch Start --- period={args.period} interval={args.interval}')

    eur_df = fetch_yfinance(TICKER_EUR, period=args.period, interval=args.interval)
    usd_df = fetch_yfinance(TICKER_USD, period=args.period, interval=args.interval)
    
    # UŻYWAMY TEJ SAMEJ FUNKCJI CO DAG!
    rows = prepare_rows(eur_df, usd_df)
    
    print(f'Prepared {len(rows)} rows. Inserting...')
    upsert_rows(rows)
    print('--- Manual Fetch Done ---')