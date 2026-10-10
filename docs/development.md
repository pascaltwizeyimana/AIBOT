# Development guide

## Local workflow

Use Python 3.12 and an isolated virtual environment. Copy `.env.example` to `.env` before starting the API. Do not put real credentials, broker details, or provider keys in committed files.

```powershell
Copy-Item .env.example .env
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pre-commit install
pytest
ruff check backend tests
ruff format --check backend tests
uvicorn backend.main:app --reload
```

## Quality gate

Before a change is accepted, it must pass tests, linting, and formatting. The GitHub Actions workflow runs the same checks on pushes and pull requests.

## API conventions

- API routes use the `/api/v1` prefix.
- Every response contains `X-Request-ID`; clients may supply their own valid correlation ID.
- API errors use `code`, `message`, `request_id`, and optional `details` fields.
- Error responses never include environment variables, credentials, MT5 account data, or stack traces.

## Runtime safety

`TRADING_MODE` defaults to `demo`. Configuration cannot turn on live trading. A later explicit, audited activation workflow will be required before any live capability is added.

### Bounded MT5 demo automation

The Execution page includes a one-click demo order and an opt-in demo automation
runner. Both require
`DEMO_EXECUTION_ENABLED=true`, an already connected MT5 **demo** account, and
`trade_allowed=true` from the terminal. It checks completed M15/H1/H4 candles,
uses broker-aware risk sizing, refuses sizes below the broker minimum, and will
not add an order while a position or pending order for that symbol exists. Each
one-click action submits at most one order. The runner accepts up to five
comma-separated broker symbols and is limited to 10 total checks, a selected
1-3 successful-order cap, a 30-second minimum interval, and 0.25% maximum risk
per order. Use Stop to end the runner; an order already submitted is not
automatically closed. Enable algorithmic trading in MT5 and confirm the broker
permits trading on the demo account; the application does not change terminal
permissions. This is a demo forward-testing tool, not historical backtesting or
a validated profitable strategy. Live accounts are rejected at both the route
and MT5 order-submission boundary.

## MT5 Phase 3 diagnostic

The terminal adapter performs only `initialize`, `version`, `last_error`, and `shutdown`. It does not call `login`, access account data, receive market data, or execute orders.

Install the optional MT5 dependency only on a Windows machine with MetaTrader 5 installed:

```powershell
python -m pip install -e ".[dev,mt5]"
```

Optionally set `MT5_TERMINAL_PATH` in `.env` to the exact `terminal64.exe` path. Run the connection test explicitly:

```powershell
python -m backend.execution.mt5_diagnostic
```

The command returns a non-zero exit code on failure and prints only connection diagnostics. It never sends credentials to `initialize`.

## MT5 Phase 4 account probe

The account probe connects to the already active terminal session, calls `account_info`, then disconnects. It never calls `login`, changes account settings, obtains prices, or sends orders. The output masks the account ID and omits the account holder name, broker server, and company.

```powershell
python -m backend.execution.mt5_account
```

For a demo account, expected fields include `"account_available": true`, `"trade_mode": "demo"`, your account currency, and balance/equity/margin values. Do not proceed if it reports `"trade_mode": "real"`.

## MT5 Phase 5 symbol discovery

The symbol discovery command calls `symbols_get` once, then disconnects. It does not call `symbol_select`, `symbol_info_tick`, `copy_rates`, or any order function.

```powershell
python -m backend.market.discover_symbols
```

The output preserves every broker symbol and identifies unambiguous logical mappings. Do not manually select a broker symbol when a mapping is marked ambiguous; a future configuration phase will require an explicit user-approved mapping.

## MT5 Phase 6 market snapshot

The market snapshot command requires an exact broker symbol and makes one read-only `symbol_info` and `symbol_info_tick` request. It does not call `symbol_select`; if the broker requires a symbol to be selected in Market Watch, select it manually in MT5 first.

```powershell
python -m backend.market.market_snapshot --symbol EURUSDm
```

The output includes bid, ask, spread, point size, spread in points, quote timestamp, and broker-provided symbol status. If no quote is returned, the platform reports `"market_status": "unknown"`; it does not claim the market is closed.

## MT5 Phase 7 historical candles

The historical command uses `copy_rates_from_pos` and returns UTC OHLCV candles ordered from oldest to newest. It excludes the currently forming candle by default (`start_pos=1`); pass `--include-current` only for display, never for signal training or backtesting features.

```powershell
python -m backend.market.historical_candles --symbol EURUSDm --timeframe H1 --count 50
```

The supported timeframes are `M1`, `M5`, `M15`, `M30`, `H1`, `H4`, `D1`, and `W1`. MT5 history is limited by what the connected terminal has available. Malformed or duplicate-time candles are rejected.

## Phase 8 technical analysis

The technical-analysis command uses completed candles only. It calculates deterministic SMA, EMA, RSI, MACD, ATR, Bollinger Bands, and Stochastic values; it does not generate a trade signal or guarantee an outcome.

```powershell
python -m backend.signals.analyze_technical --symbol EURUSDm --timeframe H1 --count 100
```

When there is insufficient history for an indicator, its output is `null`. Do not treat an indicator as a trade decision; market-structure, news, spread, and risk validation are later phases.
