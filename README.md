# Forex Project

1. Setting initial revision
docker compose up -d db
docker compose run --rm backend sh -lc "cd /app && alembic -c /app/alembic.ini revision --autogenerate -m 'initial'"
2. Applying migration
docker compose run --rm migrate
3. Enabling the rest
docker compose up -d backend worker frontend


docker compose run --rm worker python fetcher/fetch_rates.py --period 30d --interval 15m

docker compose exec db psql -U forex -d forexdb -c "SELECT count(*) FROM public.historical_currency;"

-- to restart everything (with containers deletion)
docker compose down -v 

-- AIRFLOW
docker compose up -d db airflow-db
docker compose up -d airflow-init
docker compose up -d airflow-webserver airflow-scheduler