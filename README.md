# Forex Project

Short README — how to run and what each folder does

Requirements
- Docker & Docker Compose
- (optional) access to the project .env file with database credentials

Quick start (development)
0. Build Docker images (recommended before first run or after Dockerfile changes):

	docker compose build

1. Start database only (to create migrations if needed):

	docker compose up -d db

2. Create / autogenerate an Alembic revision (only if you changed models):

	 docker compose run --rm backend sh -lc "cd /app && alembic -c /app/alembic.ini revision --autogenerate -m 'initial'"

3. Apply migrations (run the migrate container):

	 docker compose run --rm migrate

4. Start the rest of the stack:

	 docker compose up -d backend frontend predictor airflow-init airflow-webserver airflow-scheduler

Useful commands
- Run the manual fetcher (insert historical rates):

	docker compose run --rm worker python fetcher/fetch_rates.py --period 30d --interval 15m

- Inspect DB row count:

	docker compose exec db psql -U forex -d forexdb -c "SELECT count(*) FROM public.historical_currency;"

- Recreate everything (destructive, removes volumes):

	docker compose down -v

Airflow
- To initialize Airflow DB / dags the project provides an `airflow-init` service. Start it with:

	docker compose up -d airflow-init

- Then start webserver and scheduler:

	docker compose up -d airflow-webserver airflow-scheduler

How components work (short)
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

If you want, I can:
- Replace `backend/ml/train.py` with a thin wrapper that imports `ml.train.main()` (safe consolidation).
- Add a short developer `README` section with common debug commands (how to tail logs, how to run the trainer manually inside a container).

---
Last verified: project files updated and small runtime fixes applied (comments -> English). If you want I can continue by consolidating training scripts or adding simple tests.