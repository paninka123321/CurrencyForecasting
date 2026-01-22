# Forex Project

Short README — how to run and what each folder does

Requirements
- Docker & Docker Compose
- (optional) access to the project .env file with database credentials

Quick start (development)
0. Build Docker images (recommended before first run or after Dockerfile changes):

	docker compose build

1. Start database only (to create migrations if needed):

	docker compose up -d 
    docker compose up -d airflow-init
    docker compose up -d airflow-db airflow-webserver

2. Create / autogenerate an Alembic revision (only if you changed models):

	 docker compose run --rm backend sh -lc "cd /app && alembic -c /app/alembic.ini revision --autogenerate -m 'initial'"

3. Apply migrations (run the migrate container):

	 docker compose run --rm migrate

4. Start the rest of the stack:

	 docker compose up -d backend frontend predictor airflow-init airflow-webserver airflow-scheduler

Useful commands
- Run the manual fetcher (insert historical rates):


	docker compose run --rm backend sh -lc "cd /app && python fetcher/fetch_rates.py --period 30d --interval 15m"

- Inspect DB row count:

	docker compose exec db psql -U forex -d forexdb -c "SELECT count(*) FROM public.historical_currency;"

- Recreate everything (destructive, removes volumes):

	docker compose down -v

Airflow
- To initialize Airflow DB / dags the project provides an `airflow-init` service. Start it with:

	docker compose up -d airflow-init

- Then start webserver and scheduler:

	docker compose up -d airflow-webserver airflow-scheduler

How components work 
- `ml/train.py` — canonical training script. Trains candidate models, selects a winner, saves model package files into `models/` (atomic write), and inserts metrics into `model_metrics` table.
- `backend/ml/live_predictor.py` — long-running predictor process. It:
	- watches `models/live_package_*.joblib` and reloads them when updated,
	- pulls 1m prices (yfinance) into a rolling buffer, runs a prediction every minute once the buffer has 10 values,
	- writes per-minute predictions to `predictions_eurpln` and `predictions_plneur` tables.
- `airflow/dags/forex_pipeline.py` — Airflow DAG that: fetches historical rates, validates and retains data, runs the trainer (`ml.train.main()`) on a schedule (configured to every 15 minutes), and writes a 15-minute forecast to `currency_forecast`.
- `backend/` — Django backend (API). Exposes endpoints used by the frontend (chart data, metrics, history).
- `frontend/` — React dev server (UI). Connects to the backend API to display charts and model metrics.
- `migrate` / `alembic/` — DB migrations for SQLAlchemy metadata (keep schema changes here).

Where files/data live
- Model packages: `models/live_package_eurpln.joblib` and `models/live_package_plneur.joblib`
- Important DB tables: `historical_currency`, `model_metrics`, `predictions_eurpln`, `predictions_plneur`, `currency_forecast`

Notes & tips
- The predictor waits until it collects 10 one-minute samples before making the first per-minute prediction. After that it runs once per minute.
- Airflow DAG retrains models on the schedule defined in `airflow/dags/forex_pipeline.py` (defaults to every 15 minutes).
- Keep `ml/train.py` as the single source of truth for training logic — the DAG imports this module.

Troubleshooting Alembic / common issues
--------------------------------------
- If `alembic revision --autogenerate` fails with "Target database is not up to date", it means the DB does not have the current alembic revision recorded. Fix this by first applying existing migrations (upgrade head), then generate new revisions.

- Apply migrations (upgrade DB to the latest revision):

	docker compose run --rm migrate alembic upgrade head

	If the `migrate` image does not expose alembic, run from the backend container:

	docker compose run --rm backend sh -lc "cd /app && alembic -c /app/alembic.ini upgrade head"

- After a successful upgrade, verify the alembic revision in the DB:

	docker compose exec db psql -U forex -d forexdb -c "SELECT * FROM alembic_version;"

- If you intentionally know the DB already matches your migrations but the `alembic_version` table is missing, you can (with caution) stamp the DB as current:

	docker compose run --rm backend sh -lc "cd /app && alembic -c /app/alembic.ini stamp head"

	WARNING: `stamp head` does NOT run migrations — it only records the revision. Use only if you understand your DB schema.

Verify DB migration state
-------------------------
- List migration files in the container (for inspection):

	docker compose run --rm backend sh -lc "ls -la /app/backend/alembic/versions || ls -la /app/alembic/versions"

- If a migration file exists (e.g. in `backend/alembic/versions`) but the DB lacks `alembic_version`, run `upgrade head` (see above).

Testing & verification (quick)
-----------------------------
- Check that model packages are present (predictor reads these):

	docker compose exec backend ls -la /app/models

- Tail predictor logs and watch for reload/predict lines:

	docker compose logs -f predictor

