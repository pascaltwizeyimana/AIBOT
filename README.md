# AI-Powered MT5 Multi-Asset Trading Platform

Safety-first platform for analysis, demo/paper trading, and eventually controlled live MT5 execution.

## Phase 1 status

This repository currently contains only the project foundation. It does **not** connect to MetaTrader 5, retrieve market data, generate trading signals, or send orders.

The API defaults to `TRADING_MODE=demo` and rejects a configuration that enables live trading.

## Local setup

Requires Python 3.12 or newer.

```powershell
Copy-Item .env.example .env
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pytest
ruff check backend tests
ruff format --check backend tests
uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for local API documentation. The initial health endpoint is `GET /api/v1/health`.

## Optional local database

Set a non-default `POSTGRES_PASSWORD` in `.env`, then run:

```powershell
docker compose up -d postgres
```

Database integration begins in a later phase; this container is not required to run the current API or tests.

## Safety principles

- Live trading is disabled by default and cannot be enabled through the frontend.
- Trading logic will remain separate from broker execution adapters.
- Every future order must pass independent risk and execution validation.
- A signal is not a promise of profit.

For development workflow and API conventions, see [docs/development.md](docs/development.md).
