"""create historical_currency table

Revision ID: 0001_create_historical_currency
Revises: 
Create Date: 2025-12-07 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_create_historical_currency'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'historical_currency',
        sa.Column('date', sa.DateTime(), primary_key=True, nullable=False),
        sa.Column('eurpln', sa.Numeric(18,8), nullable=True),
        sa.Column('usdpln', sa.Numeric(18,8), nullable=True),
    )

def downgrade():
    op.drop_table('historical_currency')
