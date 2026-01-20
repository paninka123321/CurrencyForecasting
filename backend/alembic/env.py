from logging.config import fileConfig
import os
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from pathlib import Path
import sys

# add sql_app to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from sql_app import models
from sql_app.db import DATABASE_URL

config = context.config
fileConfig(config.config_file_name)

target_metadata = models.metadata

def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and reflected and name not in target_metadata.tables:
        return False
    return True

def run_migrations_offline():
    url = DATABASE_URL
    context.configure(url=DATABASE_URL, target_metadata=target_metadata, literal_binds=True, include_object=include_object)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        {'sqlalchemy.url': DATABASE_URL},
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, include_object=include_object)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()