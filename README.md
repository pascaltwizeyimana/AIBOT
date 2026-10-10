# PACBOT

An explainable, safety-first foundation for multi-asset market analysis and future MetaTrader 5 (MT5) workflows.

> **Current status:** This project is under active development. Live automation is opt-in, manually armed, and must not be treated as financial advice or a promise of profit.

## What this project does

The platform is being built to help people inspect market data, evaluate technical conditions, and eventually test trading ideas in controlled environments. Its design keeps analysis, risk decisions, and broker execution separate so that each step can be inspected and tested.

Today, the repository provides:

- A FastAPI service with validated settings and structured error responses.
- A safe health endpoint at `GET /api/v1/health`.
- Explicit, read-only MT5 diagnostics and account inspection tools.
- Broker symbol discovery, market snapshots, and historical OHLCV candles.
- Deterministic technical indicators including SMA, EMA, RSI, MACD, ATR, Bollinger Bands, and Stochastic.
- Automated tests, linting, formatting checks, and development documentation.
- A bounded MT5 demo-account signal runner with explicit start/stop controls and order limits.
- A React dashboard for market research and manually armed live automation controls.

Live execution is opt-in and remains disabled by default. When explicitly enabled, the app offers a manually armed live automation worker that:

- Sizes each order using current account equity and broker tick economics.
- Requires a stop loss and take profit on every submitted market order.
- Stops on configured per-order, aggregate open-risk, position-count, order-count, and session drawdown limits.
- Halts if existing position risk is unknown or pending broker orders are present.
- Requires a connected real MT5 account and explicit in-app arming; opening the app does not start trading.
- Uses deterministic multi-timeframe technical rules; it is not a self-learning model or a guarantee of profitable decisions.
- Runs for at most the configured order count (default three), then disarms; it does not restart automatically.
- Blocks new XAUUSD trades within 30 minutes before or after any high-impact USD event.
- Fails closed for XAUUSD when the configured calendar feed is missing, stale, or invalid; other symbols are unaffected by this XAUUSD-specific filter.

The default caps are 0.25% risk per order, 0.75% aggregate open risk, three concurrent positions, three orders per run, 1% session equity drawdown, and 0.01 lots per order. These are conservative code defaults, not guarantees against loss or a recommendation to trade.

Today, it does **not**:

- Start live trading automatically when the desktop app opens.
- Guarantee profitable decisions or provide financial advice.
- Claim that an indicator or signal will be profitable.
- Require a database, Redis, MT5 terminal, or broker account to run the API and tests.

## Safety first

The default runtime mode is `demo`, and live execution remains disabled unless all explicit environment gates and the confirmation phrase are configured. Starting the desktop app never arms the bot: an operator must review the real account and press **ARM LIVE AUTOMATION** in the app. Each order is re-sized from current equity and broker tick economics, and the worker stops at its session limits. These safeguards reduce specific risks but cannot guarantee execution price, broker acceptance, or a maximum realized loss.

The live workflow is deliberately staged:

1. Read and validate market data.
2. Produce transparent analysis with the inputs and assumptions visible.
3. Apply independent risk checks.
4. Require an explicit, audited execution boundary before any broker action.

Never commit credentials or real account details to this repository. Do not enable live execution until the limits, symbol names, and broker behavior have been independently reviewed.

## How the pieces fit together

```text
Client or developer
	|
	v
FastAPI application (/api/v1)
	|
	+--> Health and error handling
	+--> Market and technical-analysis services
	+--> Read-only MT5 adapters and command-line diagnostics
	+--> Future risk and execution boundaries
	|
	+--> Future persistence (PostgreSQL)
```

Important directories:

| Directory | Responsibility |
| --- | --- |
| `backend/api` | Versioned HTTP routes and response contracts |
| `backend/config` | Environment-based, validated application settings |
| `backend/execution` | MT5 terminal lifecycle and read-only probes |
| `backend/market` | Symbols, snapshots, candles, and market models |
| `backend/signals` | Technical-analysis calculations |
| `backend/tests` and `tests` | Automated tests |
| `docs` | Development workflow and detailed MT5 phase notes |

## Quick start on Windows

### Requirements

- Windows with PowerShell
- Python 3.12 or newer
- Git
- Docker Desktop only if you want the optional PostgreSQL container

### Install and run

From the repository root:

```powershell
Copy-Item .env.example .env
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run the quality checks:

```powershell
pytest
ruff check backend tests
ruff format --check backend tests
```

Start the local API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Start the React frontend in a second PowerShell window:

```powershell
Push-Location frontend
npm run dev -- --host 127.0.0.1
Pop-Location
```

The API uses real MT5 data when the installed MetaTrader 5 terminal is available. If MT5 cannot
initialize or a quote/history read fails, routes return an explicit unavailable response and the
frontend shows `NO FEED` / `MT5 DISCONNECTED`; no synthetic market prices are generated.

### Open the app from a Desktop icon

After completing the install steps above, create a Windows Desktop shortcut once:

```powershell
powershell -ExecutionPolicy Bypass -File .\Create-Desktop-Shortcut.ps1
```

Double-click **PACBOT** on the Desktop to start the local API and dashboard. The
launcher opens the dashboard in an Edge app window when Edge is installed; otherwise it uses your
default browser. The API and frontend start without console windows. Live automation controls are
in **Execution** and require explicit live environment gates, a connected real MT5 account, and an
in-app arm action. Closing the dashboard does not guarantee that the backend worker has stopped;
use **STOP LIVE AUTOMATION** before closing the app.

Then open:

- Interactive API documentation: <http://127.0.0.1:8000/docs>
- Alternative API documentation: <http://127.0.0.1:8000/redoc>
- Health check: <http://127.0.0.1:8000/api/v1/health>

Example health response:

```json
{
  "status": "ok",
  "environment": "development",
  "trading_mode": "demo",
  "live_trading_enabled": false
}
```

Every API response also carries an `X-Request-ID` response header. Clients may provide their own value for request tracing.

## Configuration

Configuration is loaded from environment variables and the optional `.env` file. Start with `.env.example`; do not commit `.env`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `development` | Runtime environment label |
| `LOG_LEVEL` | `INFO` | Application log level |
| `API_HOST` | `127.0.0.1` | API bind address |
| `API_PORT` | `8000` | API port |
| `TRADING_MODE` | `demo` | Permitted mode: `demo`, `paper`, or explicitly enabled `live` |
| `LIVE_TRADING_ENABLED` | `false` | First explicit live-execution gate |
| `TRADING_EXECUTION_ENABLED` | `false` | Separate live execution gate |
| `LIVE_TRADING_CONFIRMATION` | empty | Must equal `I_UNDERSTAND_LIVE_TRADING` to enable live mode |
| `MAX_LIVE_LOTS` | `0.01` | Maximum broker volume per live order |
| `LIVE_AUTO_MAX_RISK_PERCENT` | `0.25` | Maximum equity risk for each automated live order |
| `LIVE_AUTO_MAX_SESSION_LOSS_PERCENT` | `1.0` | Session drawdown threshold that disarms the bot |
| `LIVE_AUTO_MAX_OPEN_RISK_PERCENT` | `0.75` | Aggregate risk budget across open positions |
| `LIVE_AUTO_MAX_POSITIONS` | `3` | Maximum concurrent positions |
| `LIVE_AUTO_MAX_ORDERS` | `3` | Maximum submitted orders in one run |
| `ECONOMIC_CALENDAR_URL` | empty | Operator-provided JSON economic-calendar feed; required to allow XAUUSD entries |
| `ECONOMIC_CALENDAR_TIMEOUT_SECONDS` | `5` | Maximum calendar request duration |
| `ECONOMIC_CALENDAR_MAX_AGE_SECONDS` | `900` | Maximum feed age accepted before XAUUSD is blocked |
| `MT5_TERMINAL_PATH` | empty | Optional path to `terminal64.exe` |
| `MT5_CONNECTION_TIMEOUT_MS` | `60000` | MT5 connection timeout |

Database and Redis variables are included as placeholders for later phases. They are not required by the current API.

### Economic calendar feed

The project does not include a calendar vendor or API key. Configure `ECONOMIC_CALENDAR_URL` to a trusted endpoint that returns this JSON shape, with ISO-8601 timestamps containing a timezone:

```json
{
	"updated_at": "2026-09-30T12:00:00Z",
	"events": [
		{
			"event": "Consumer Price Index",
			"currency": "USD",
			"impact": "high",
			"time": "2026-09-30T12:20:00Z"
		}
	]
}
```

The feed's `updated_at` must be no older than `ECONOMIC_CALENDAR_MAX_AGE_SECONDS`. Before each XAUUSD analysis, the bot checks high-impact USD events against the current UTC time. An event from 30 minutes ago through 30 minutes ahead blocks a new entry. On the next evaluation after the window ends, the bot fetches the feed again and reruns the technical setup; it can then return BUY, SELL, or NO TRADE. An unavailable or stale feed blocks XAUUSD rather than assuming the calendar is clear.

## Optional MT5 read-only tools

MT5 tools require a Windows machine with MetaTrader 5 installed. Install the optional dependency with:

```powershell
python -m pip install -e ".[dev,mt5]"
```

The tools connect to the active terminal session and disconnect after each operation. They do not call the MT5 login function or send orders.

```powershell
# Check terminal availability and version
python -m backend.execution.mt5_diagnostic

# Inspect the active account without exposing its full ID
python -m backend.execution.mt5_account

# List and map broker-provided symbols
python -m backend.market.discover_symbols

# Read one broker symbol's current snapshot
python -m backend.market.market_snapshot --symbol EURUSDm

# Read completed H1 candles
python -m backend.market.historical_candles --symbol EURUSDm --timeframe H1 --count 50

# Calculate technical indicators from completed candles
python -m backend.signals.analyze_technical --symbol EURUSDm --timeframe H1 --count 100
```

Use the exact symbol name exposed by your broker. MT5 history depends on what the connected terminal has available. The technical-analysis command reports missing values when there is not enough history; it does not turn indicators into an automatic trade decision.

See [docs/development.md](docs/development.md) for the behavior and safety limits of each MT5 phase.

## Optional PostgreSQL container

Database integration is planned for a later phase. It is not needed for the current API or tests. To start the local container, first replace the example password in `.env` with a non-default value, then run:

```powershell
docker compose up -d postgres
```

Stop it with:

```powershell
docker compose down
```

## Development workflow

Before opening a pull request, run tests, linting, and formatting checks. Install the repository hooks once with:

```powershell
pre-commit install
```

The project uses Python type-friendly models, a versioned API prefix, structured errors, and request IDs for traceability. Detailed conventions are documented in [docs/development.md](docs/development.md).

## Roadmap

The implementation is intentionally incremental:

- Complete the analysis and market-data foundation.
- Add persistence for market observations, analyses, and audit records.
- Add paper-trading workflows with reproducible results.
- Add independent risk validation and approval controls.
- Consider controlled broker execution only after the preceding layers are tested, observable, and explicitly reviewed.

## License and financial disclaimer

No license file is currently declared in this repository. Do not redistribute the project until its licensing terms are defined.

This software is for research and development. Financial markets involve substantial risk, and past performance does not predict future results. Nothing in this repository is financial, investment, or trading advice.
