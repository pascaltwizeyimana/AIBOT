export interface Health {
  status: string;
  environment: string;
  trading_mode: string;
  live_trading_enabled: boolean;
}

export interface Capabilities {
  database_configured: boolean;
  execution_available: boolean;
  demo_execution_available: boolean;
  live_trading_available: boolean;
  market_data_available: boolean;
  news_data_available: boolean;
  message: string;
}

export interface TimeframeAnalysis {
  timeframe: string;
  trend: "bullish" | "bearish" | "neutral";
  structure: string;
  volatility: string;
  atr: number | null;
  atr_percent: number | null;
  support: number | null;
  resistance: number | null;
  liquidity: string[];
  reasons: string[];
}

export interface AnalysisCandidate {
  broker_symbol: string;
  decision: "buy" | "sell" | "no_trade";
  confidence: string;
  timeframe_analyses: TimeframeAnalysis[];
  reasons: string[];
  disclaimer: string;
  data_source?: "mt5" | "development_demo";
  trade_plan?: {
    action: string;
    entry: number | null;
    stop_loss: number | null;
    take_profit: number | null;
    risk_reward: string | null;
    why: string[];
  };
  technical?: TechnicalSnapshot[];
  market_structure?: MarketStructure[];
}

export interface TechnicalSnapshot {
  timeframe: string;
  ema_20: number | null;
  rsi_14: number | null;
  macd_line: number | null;
  macd_signal: number | null;
  macd_histogram: number | null;
  atr_14: number | null;
}

export interface MarketStructure {
  timeframe: string;
  bos: string | null;
  choch: string | null;
  fvg: Array<{ side: string; low: number; high: number }>;
  order_blocks: Array<{ side: string; low: number; high: number }>;
}

export interface PaperOrder {
  id: number;
  symbol: string;
  side: "buy" | "sell";
  quantity: number;
  entry_price: number;
  status: "open" | "closed";
  exit_price: number | null;
  realized_pnl: number;
}

export interface PaperAccount {
  mode: string;
  starting_balance: number;
  cash: number;
  equity: number;
  realized_pnl: number;
  unrealized_pnl: number;
  total_pnl: number;
  open_orders: PaperOrder[];
  closed_orders: PaperOrder[];
}

export interface DemoTradeResult {
  executed: boolean;
  reason?: string;
  side?: string;
  symbol?: string;
  volume?: number;
  entry?: number;
  stop_loss?: number;
  take_profit?: number;
  order?: { submitted: boolean; ticket: number | null; error_message: string | null };
}

export interface DemoAutoTradeStatus {
  running: boolean;
  status: string;
  symbol?: string;
  symbols?: string[];
  risk_percent?: number;
  interval_seconds?: number;
  max_orders?: number;
  evaluations?: number;
  orders_submitted?: number;
  last_result?: { executed: boolean; reason?: string; side?: string; volume?: number } | null;
  last_error?: string | null;
}

export interface LiveAutoTradeStatus {
  running: boolean;
  status: string;
  symbols?: string[];
  risk_percent?: number;
  interval_seconds?: number;
  starting_equity?: number;
  evaluations?: number;
  orders_submitted?: number;
  last_result?: { executed: boolean; reason?: string; side?: string; symbol?: string; volume?: number; risk_amount?: number } | null;
  last_error?: string | null;
}

export interface BrokerSymbol {
  broker_symbol: string;
  logical_symbol: string | null;
  visible: boolean;
  selected: boolean;
  path: string | null;
  trade_mode: number | null;
}

export interface SymbolCatalog {
  symbols: BrokerSymbol[];
  unambiguous_mappings: Record<string, string>;
  ambiguous_mappings: Record<string, string[]>;
}

export interface MarketQuote {
  broker_symbol: string;
  quote_available: boolean;
  market_status: string;
  observed_at: string | null;
  bid: number | null;
  ask: number | null;
  spread: number | null;
  digits: number | null;
}

export interface Candle {
  open_time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  tick_volume: number;
}

export interface CandleSeries {
  broker_symbol: string;
  timeframe: string;
  includes_current_candle: boolean;
  candles: Candle[];
}

export interface Mt5Status {
  connected: boolean;
  package_available: boolean;
  terminal_version: string | null;
  error_message: string | null;
  last_update: string | null;
}

export interface Mt5Account {
  connected: boolean;
  account_available: boolean;
  account_id_masked: string | null;
  trade_mode: string | null;
  currency: string | null;
  balance: number | null;
  equity: number | null;
  margin: number | null;
  margin_free: number | null;
  margin_level: number | null;
  trading_allowed: boolean | null;
  error_message: string | null;
  positions: Mt5Position[];
  orders: Mt5PendingOrder[];
  last_update: string | null;
}

export interface Mt5Position {
  ticket: number;
  symbol: string;
  side: string;
  volume: number | null;
  price_open: number | null;
  price_current: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  profit: number | null;
  time: string | null;
}

export interface Mt5PendingOrder {
  ticket: number;
  symbol: string;
  order_type: string;
  volume: number | null;
  price_open: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  time_setup: string | null;
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`);
  if (!response.ok) throw new Error(`Service unavailable (${response.status})`);
  return response.json() as Promise<T>;
}

async function post<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const error = (await response.json().catch(() => ({}))) as { message?: string; detail?: string };
    throw new Error(error.message ?? error.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const getHealth = () => get<Health>("/health");
export const getCapabilities = () => get<Capabilities>("/capabilities");
export const getSymbolCatalog = () => get<SymbolCatalog>("/market/symbols");
export const getMarketQuote = (symbol: string) =>
  get<MarketQuote>(`/market/snapshots/${encodeURIComponent(symbol)}`);
export const getCandles = (symbol: string, timeframe: string, count = 120) =>
  get<CandleSeries>(`/market/candles/${encodeURIComponent(symbol)}/${timeframe}?count=${count}`);
export const getMt5Status = () => get<Mt5Status>("/mt5/status");
export const getMt5Account = () => get<Mt5Account>("/mt5/account");
export const getAnalysis = (symbol: string, timeframes = "M15,H1,H4") =>
  get<AnalysisCandidate>(`/analysis/${encodeURIComponent(symbol)}?timeframes=${encodeURIComponent(timeframes)}&count=250`);
export const getPaperAccount = () => get<PaperAccount>("/paper/account");
export const createPaperOrder = (symbol: string, side: "buy" | "sell", quantity: number) =>
  post<{ account: PaperAccount }>("/paper/orders", { symbol, side, quantity }).then((result) => result.account);
export const createAutoBatch = (symbol: string, quantity: number, orders: number) =>
  post<PaperAccount>("/paper/auto", { symbol, quantity, orders });
export const closePaperOrders = () => post<PaperAccount>("/paper/close-all");
export const resetPaperAccount = () => post<PaperAccount>("/paper/reset");
export const analyseAndTradeDemo = (symbol: string, volume: number) =>
  post<DemoTradeResult>("/demo-execution/analyse-and-trade", { symbol, volume });
export const getDemoAutoTradeStatus = () =>
  get<DemoAutoTradeStatus>("/demo-execution/auto/status");
export const manualDemoTrade = (
  symbol: string,
  side: "buy" | "sell",
  volume: number,
  entry: number,
  stopLoss: number,
  takeProfit: number,
) =>
  post<DemoTradeResult>("/demo-execution/manual", {
    symbol,
    side,
    volume,
    entry,
    stop_loss: stopLoss,
    take_profit: takeProfit,
  });
export const oneClickDemoTrade = (symbol: string, riskPercent = 0.25) =>
  post<DemoTradeResult>("/demo-execution/one-click", { symbol, risk_percent: riskPercent });
export const startDemoAutoTrade = (symbols: string[], riskPercent = 0.25, intervalSeconds = 60, maxOrders = 1) =>
  post<DemoAutoTradeStatus>("/demo-execution/auto/start", {
    symbols,
    risk_percent: riskPercent,
    interval_seconds: intervalSeconds,
    max_orders: maxOrders,
  });
export const stopDemoAutoTrade = () =>
  post<DemoAutoTradeStatus>("/demo-execution/auto/stop");
export const analyseAndTradeLive = (symbol: string, riskPercent: number, confirmation: string) =>
  post<DemoTradeResult & { risk_amount?: number }>("/live-execution/analyse-and-trade", { symbol, risk_percent: riskPercent, confirmation });
export const getLiveAutoTradeStatus = () => get<LiveAutoTradeStatus>("/live-execution/auto/status");
export const startLiveAutoTrade = (symbols: string[], riskPercent: number, intervalSeconds: number, confirmation: string) =>
  post<LiveAutoTradeStatus>("/live-execution/auto/start", {
    symbols,
    risk_percent: riskPercent,
    interval_seconds: intervalSeconds,
    confirmation,
  });
export const stopLiveAutoTrade = () => post<LiveAutoTradeStatus>("/live-execution/auto/stop");
export const manualLiveTrade = (
  symbol: string,
  side: "buy" | "sell",
  volume: number,
  riskPercent: number,
  entry: number,
  stopLoss: number,
  takeProfit: number,
  confirmation: string,
) =>
  post<DemoTradeResult>("/live-execution/manual", {
    symbol,
    side,
    volume,
    risk_percent: riskPercent,
    entry,
    stop_loss: stopLoss,
    take_profit: takeProfit,
    confirmation,
  });
