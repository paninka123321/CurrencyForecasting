## Step 1: Full shutdown and cleanup

This command stops all containers and removes volumes (databases will be wiped).

```Bash
docker compose down -v
```

Step 2: Build images and prepare databases
First, build the images, then start only the databases so migrations can be applied.

```Bash
docker compose build
```

# Uruchomienie baz danych i inicjalizacja Airflow

```Bash
docker compose up -d db airflow-db
docker compose up -d airflow-init
```

Step 3: Schema migrations (Alembic)
Once the databases are running, we need to create the tables.

```Bash
docker compose up migrate
```

Step 4: Start the full stack
Now bring up all remaining services.

```Bash
docker compose up -d backend frontend predictor airflow-webserver airflow-scheduler
```

Step 5: Fetch initial data
After startup, the database is empty. To avoid an empty dashboard, fetch historical data (e.g. last 30 days):

```Bash
docker compose run --rm backend sh -lc "cd /app && python fetcher/fetch_rates.py --period 30d --interval 15m"
```

Quick verification
If you want to check whether data has actually been inserted into the database, use:

