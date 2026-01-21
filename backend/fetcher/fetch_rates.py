#!/usr/bin/env python
import os
import argparse
from pathlib import Path
from dotenv import load_dotenv
import yfinance as yf
import pandas as pd
from decimal import Decimal
from sqlalchemy.dialects.postgresql import insert as pg_insert

# Ensure these imports work in your project layout
# When running via Docker, PYTHONPATH in the container should handle this
from sql_app.db import engine
from sql_app.models import historical_currency

# Ładowanie zmiennych środowiskowych
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / '.env')

TICKER_EUR = os.getenv('TICKER_EUR', 'EURPLN=X')
TICKER_USD = os.getenv('TICKER_USD', 'USDPLN=X')

def fetch_yfinance(ticker: str, period: str, interval: str):
    """
    Fetch data from Yahoo Finance and normalize timezones.
    """
    print(f"Fetching {ticker} (period={period}, interval={interval})...")
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=period, interval=interval)
        
        if df.empty:
            print(f"Warning: Empty dataframe for {ticker}")
            return pd.DataFrame()

        # Remove timezone info (convert to naive UTC) so Postgres accepts timestamps.
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
    Merge EUR and USD data into a single format ready for DB insertion.
    """
    if eur_df.empty and usd_df.empty:
        return []

    # Concatenate on the index (time)
    # axis=1 means columns are joined side-by-side for the same timestamps
    df = pd.concat([eur_df, usd_df], axis=1)
    
    # Usuwamy wiersze, gdzie obie waluty są NaN
    df = df.dropna(how='all')
    
    # Extract the date from the index into a column
    df = df.reset_index()
    
    # Ensure the column containing the date is named 'date'
    # (reset_index may call it 'Date' or 'index')
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
            # Convert pandas timestamp to native python datetime
            date_val = pd.to_datetime(r['date']).to_pydatetime()

            eurv = r.get(TICKER_EUR)
            usdv = r.get(TICKER_USD)

            # Convert to Decimal (safer for currency values)
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
    Insert rows into the DB. If a row for the date exists -> update rates.
    """
    if not rows:
        print('No rows to insert')
        return

    # Use a context manager (with engine.begin) which commits or rollbacks automatically
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