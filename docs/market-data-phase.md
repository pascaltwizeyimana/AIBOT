# Read-only MT5 market-data phase

The API now exposes no-trade, read-only market routes:

- `GET /api/v1/market/symbols`
- `GET /api/v1/market/snapshots/{broker_symbol}`
- `GET /api/v1/market/candles/{broker_symbol}/{timeframe}?count=200`

The routes never call MT5 login, `symbol_select`, or an order function. Candle requests exclude the forming candle. An unavailable terminal, unavailable package, unavailable quote, or unavailable history returns HTTP 503; it is never replaced by sample data.

Quote snapshots are rejected when their MT5 timestamp exceeds `MARKET_DATA_MAX_AGE_SECONDS` (10 seconds by default).

Install the optional dependency only on a Windows system with MetaTrader 5 installed:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,mt5]"
```

Set `MT5_TERMINAL_PATH` only if the terminal cannot be located automatically, then use the API documentation at `http://127.0.0.1:8000/docs` to validate your active **demo** terminal.

## Deterministic analysis

`GET /api/v1/analysis/{broker_symbol}?timeframes=M15,H1,H4&count=250` retrieves completed candles for each requested timeframe and returns trend, ATR volatility, swing-based support/resistance, BOS/CHOCH classifications, equal-high/equal-low liquidity observations, and an explainable candidate.

The candidate is never an order. Conflicting evidence, high volatility, unavailable history, news risk, and all risk checks must result in `NO_TRADE` when those later layers are added.
