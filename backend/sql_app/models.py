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

# currency_forecast = Table(
#     'currency_forecast',
#     metadata,
#     Column("id", Integer, primary_key=True),
#     Column("symbol", String, nullable=False),
#     Column("forecast_time", DateTime(timezone=True), nullable=False),
#     Column("predicted_close", Numeric(18, 8), nullable=False),
#     Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
# )