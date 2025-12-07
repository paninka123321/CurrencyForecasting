#!/usr/bin/env python
import os
from pathlib import Path
from dotenv import load_dotenv
import yfinance as yf
import pandas as pd
from decimal import Decimal
from sql_app.db import engine
from sql_app.models import historical_currency
from sqlalchemy.dialects.postgresql import insert as pg_insert


load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / '.env.example')

TICKER_EUR = os.getenv('TICKER_EUR', 'EURPLN=X')
TICKER_USD = os.getenv('TICKER_USD', 'USDPLN=X')


def fetch_hourly_yfinance(ticker):
    t = yf.Ticker(ticker)
    
    # get 1 year hourly history
    df = t.history(period='1y', interval='1h')
    if df.empty:
        return pd.DataFrame()
    # ensure UTC naive timestamps
    idx = df.index
    if getattr(idx, 'tz', None) is not None:
        idx = idx.tz_convert('UTC').tz_localize(None)
    df = df.copy()
    df.index = idx
    df = df[['Close']].rename(columns={'Close': ticker})
    return df


def prepare_rows(eur_df, usd_df):
    df = pd.concat([eur_df, usd_df], axis=1)
    df = df.dropna(how='all')
    df = df.reset_index().rename(columns={'index': 'date'})
    rows = []
    for _, r in df.iterrows():
        dt = r['index'] if 'index' in r else r['Date'] if 'Date' in r else r['date']
        # ensure dt is a python datetime
        date = pd.to_datetime(r['date']).to_pydatetime()
        eurv = r.get(TICKER_EUR)
        usdv = r.get(TICKER_USD)
        eur = Decimal(str(eurv)) if pd.notna(eurv) else None
        usd = Decimal(str(usdv)) if pd.notna(usdv) else None
        rows.append({'date': date, 'eurpln': eur, 'usdpln': usd})
    return rows


def upsert_rows(rows):
    if not rows:
        print('No rows to insert')
        return
    # ensure table exists
    try:
        historical_currency.metadata.create_all(engine)
    except Exception:
        pass
    conn = engine.connect()
    try:
        stmt = pg_insert(historical_currency).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=['date'],
            set_={'eurpln': stmt.excluded.eurpln, 'usdpln': stmt.excluded.usdpln}
        )
        conn.execute(stmt)
        conn.commit()
    finally:
        conn.close()


if __name__ == '__main__':
    print('Fetching hourly history via yfinance...')
    eur_df = fetch_hourly_yfinance(TICKER_EUR)
    usd_df = fetch_hourly_yfinance(TICKER_USD)
    if eur_df.empty and usd_df.empty:
        print('No data fetched from yfinance')
    else:
        # align column names to ticker strings
        eur_df = eur_df.rename(columns={TICKER_EUR: TICKER_EUR})
        usd_df = usd_df.rename(columns={TICKER_USD: TICKER_USD})
        rows = []
        if not eur_df.empty and not usd_df.empty:
            merged = pd.concat([eur_df, usd_df], axis=1)
        else:
            merged = eur_df.join(usd_df, how='outer')
        merged = merged.dropna(how='all')
        merged = merged.reset_index()
        # ensure we have a `date` column regardless of the index name
        if 'date' not in merged.columns:
            # the index column will be the first column after reset_index()
            idx_col = merged.columns[0]
            if idx_col != 'date':
                merged = merged.rename(columns={idx_col: 'date'})

        for _, r in merged.iterrows():
            # parse date robustly
            try:
                date_ts = pd.to_datetime(r['date'])
            except Exception:
                # fallback: try the first column again
                date_ts = pd.to_datetime(merged.iloc[_ , 0])
            # convert to python datetime
            try:
                date = date_ts.to_pydatetime()
            except Exception:
                date = pd.Timestamp(date_ts).to_pydatetime()

            eurv = r.get(TICKER_EUR)
            usdv = r.get(TICKER_USD)
            eur = Decimal(str(eurv)) if pd.notna(eurv) else None
            usd = Decimal(str(usdv)) if pd.notna(usdv) else None
            rows.append({'date': date, 'eurpln': eur, 'usdpln': usd})
        print(f'Prepared {len(rows)} hourly rows — inserting into DB...')
        upsert_rows(rows)
        print('Done')
