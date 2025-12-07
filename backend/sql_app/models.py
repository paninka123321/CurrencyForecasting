from sqlalchemy import Column, DateTime, Numeric, Table, MetaData

metadata = MetaData()

historical_currency = Table(
    'historical_currency',
    metadata,
    Column('date', DateTime, primary_key=True),
    Column('eurpln', Numeric(18, 8)),
    Column('usdpln', Numeric(18, 8)),
)
