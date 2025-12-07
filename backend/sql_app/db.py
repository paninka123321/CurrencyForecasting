import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / '.env.example')

DB_USER = os.getenv('DATABASE_USER')
DB_PASS = os.getenv('DATABASE_PASSWORD')
DB_NAME = os.getenv('DATABASE_NAME')
DB_HOST = os.getenv('DATABASE_HOST', 'db')
DB_PORT = os.getenv('DATABASE_PORT', '5432')

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
