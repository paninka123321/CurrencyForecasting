from sqlalchemy import Column, DateTime, Numeric, Integer, String, Table, MetaData
from sqlalchemy.sql import func

metadata = MetaData()

historical_currency = Table(
    'historical_currency',
    metadata,
    Column('date', DateTime, primary_key=True),
    Column('eurpln', Numeric(18, 8)),
    Column('usdpln', Numeric(18, 8)),
)

# Table storing model metrics (created by the training script / migrations)
model_metrics = Table(
    'model_metrics',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('pair', String(20)),
    Column('selected_model', String(100)),
    Column('mae', Numeric(18, 8)),
    Column('r2', Numeric(18, 8)),
    Column('trained_at', DateTime, server_default=func.now()),
)

# Prediction tables used by live_predictor
predictions_eurpln = Table(
    'predictions_eurpln',
    metadata,
    Column('target_date', DateTime, primary_key=True),
    Column('execution_date', DateTime),
    Column('predicted_rate', Numeric(18, 8)),
    Column('model_name', String(50)),
    Column('mae', Numeric(18, 8)),
    Column('r2', Numeric(18, 8)),
)

# Prediction table for PLN->EUR
predictions_plneur = Table(
    'predictions_plneur',
    metadata,
    Column('target_date', DateTime, primary_key=True),
    Column('execution_date', DateTime),
    Column('predicted_rate', Numeric(18, 8)),
    Column('model_name', String(50)),
    Column('mae', Numeric(18, 8)),
    Column('r2', Numeric(18, 8)),
)

# Existing forecast table
currency_forecast = Table(
    'currency_forecast',
    metadata,
    Column('date', DateTime, primary_key=True),
    Column('eurpln_pred', Numeric(18, 8)),
    Column('plneur_pred', Numeric(18, 8)),
    Column('model_version', String(50)),
    Column('created_at', DateTime, server_default=func.now()),
)

