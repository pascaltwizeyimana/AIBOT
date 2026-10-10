# Foundation phase

This phase establishes boundaries and observability. It does not connect to a broker, read prices, ingest news, create signals, or submit orders.

## Components

- `backend/domain`: pure trading concepts, including the `BUY` / `SELL` / `NO_TRADE` decision enum.
- `backend/application`: contracts for future market, news, and execution adapters.
- `backend/infrastructure/database`: opt-in SQLAlchemy persistence and an Alembic audit-event migration.
- `frontend`: a React/Vite dashboard that reads only public status endpoints.

## Commands

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check backend tests
Set-Location frontend
npm install
npm run dev
```

To run PostgreSQL, copy `.env.example` to `.env`, replace its placeholder password, then run `docker compose up -d postgres` and `..\.venv\Scripts\alembic.exe upgrade head` from the repository root.

`TRADING_EXECUTION_ENABLED=true`, `LIVE_TRADING_ENABLED=true`, and `TRADING_MODE=live` all fail settings validation. The capability endpoint deliberately reports that execution, market data, and news data are unavailable in this phase.
