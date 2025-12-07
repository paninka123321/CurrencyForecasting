# Forex Project

Prosty projekt: zbiera historyczne kursy EUR/PLN i USD/PLN i zapisuje do Postgres.

Uruchamianie (lokalnie z Dockera):

- Skopiuj `.env.example` do `.env` i dostosuj ustawienia.
```bash
cp .env.example .env
```

- Uruchom:

```bash
docker compose up --build
```

- baza danych jest w dockerze, podgląd tabeli history_currency:
```bash
docker compose exec db psql -U forex -d forexdb -c "SELECT count(*) FROM public.historical_currency;"
```
powinno byc 6229

Usługi:
- `db` - Postgres
- `backend` - Django (API do odczytu danych), korzysta z tej samej bazy
- `worker` - fetcher który pobiera dane i zapisuje do tabeli `historical_currency` przy użyciu SQLAlchemy
- `frontend` - prosty React pokazujący dane
- `airflow` - placeholder na przyszłe DAGi
- `mlmodel` - placeholder na przyszły model ML

Migracje:
- Alembic znajduje się w `backend/alembic` i zawiera migrację tworzącą tabelę `historical_currency`.

Uwaga:
- Skrypt fetchera domyślnie używa yfinance - dane /h roczne
