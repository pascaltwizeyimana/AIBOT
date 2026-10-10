import { useEffect, useMemo, useState } from "react";
import {
  AnalysisCandidate,
  BrokerSymbol,
  CandleSeries,
  Capabilities,
  DemoAutoTradeStatus,
  LiveAutoTradeStatus,
  MarketQuote,
  Mt5Account,
  Mt5Status,
  PaperAccount,
  closePaperOrders,
  createPaperOrder,
  getAnalysis,
  getCandles,
  getCapabilities,
  getDemoAutoTradeStatus,
  getLiveAutoTradeStatus,
  getMt5Account,
  getMt5Status,
  getMarketQuote,
  getPaperAccount,
  getSymbolCatalog,
  analyseAndTradeLive,
  manualDemoTrade,
  manualLiveTrade,
  oneClickDemoTrade,
  startLiveAutoTrade,
  stopLiveAutoTrade,
  resetPaperAccount,
  startDemoAutoTrade,
  stopDemoAutoTrade,
} from "./api/system";

type Section = "dashboard" | "markets" | "analysis" | "execution";
type SignalHorizon = "short" | "long";
const timeframes = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"];
const watchlist = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD", "NAS100"];

function number(value: number | null | undefined, digits = 2) {
  return value === null || value === undefined ? "--" : value.toFixed(digits);
}

export function Dashboard() {
  const [section, setSection] = useState<Section>("dashboard");
  const [symbol, setSymbol] = useState("XAUUSD");
  const [timeframe, setTimeframe] = useState("M15");
  const [symbols, setSymbols] = useState<BrokerSymbol[]>([]);
  const [quote, setQuote] = useState<MarketQuote>();
  const [candles, setCandles] = useState<CandleSeries>();
  const [status, setStatus] = useState<Mt5Status>();
  const [account, setAccount] = useState<Mt5Account>();
  const [analysis, setAnalysis] = useState<AnalysisCandidate>();
  const [horizon, setHorizon] = useState<SignalHorizon>("short");
  const [capabilities, setCapabilities] = useState<Capabilities>();
  const [notice, setNotice] = useState("");

  useEffect(() => {
    getSymbolCatalog().then((catalog) => {
      setSymbols(catalog.symbols);
      const visibleSymbol = catalog.symbols.find((item) => item.visible)?.broker_symbol;
      if (visibleSymbol) setSymbol((current) => catalog.symbols.some((item) => item.broker_symbol === current) ? current : visibleSymbol);
    }).catch(() => setNotice("MT5 symbol catalog unavailable"));
    getMt5Status().then(setStatus).catch(() => setStatus({ connected: false, package_available: false, terminal_version: null, error_message: "API unavailable", last_update: null }));
    getCapabilities().then(setCapabilities).catch(() => undefined);
  }, []);

  useEffect(() => {
    setCandles(undefined);
    let active = true;
    const analysisFrames = horizon === "short" ? "M5,M15,H1" : "H1,H4,D1";
    const refreshMarket = () => Promise.all([getCandles(symbol, timeframe), getAnalysis(symbol, analysisFrames), getMarketQuote(symbol)])
      .then(([nextCandles, nextAnalysis, nextQuote]) => { if (!active) return; setCandles(nextCandles); setAnalysis(nextAnalysis); setQuote(nextQuote); setNotice(""); })
      .catch(() => { if (active) setNotice("Live MT5 history is temporarily unavailable; retrying"); });
    refreshMarket();
    const timer = window.setInterval(refreshMarket, 15000);
    return () => { active = false; window.clearInterval(timer); };
  }, [symbol, timeframe, horizon]);

  useEffect(() => {
    const refresh = () => getMt5Account().then(setAccount).catch(() => undefined);
    refresh();
    const timer = window.setInterval(refresh, 5000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const apiHost = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1").replace(/^https?:\/\//, "");
    let socket: WebSocket | undefined;
    let retryTimer: number | undefined;
    let stopped = false;
    const connect = () => {
      if (stopped) return;
      socket = new WebSocket(`${protocol}://${apiHost}/ws/market/${encodeURIComponent(symbol)}`);
      socket.onmessage = (event) => setQuote((JSON.parse(event.data) as { snapshot?: MarketQuote }).snapshot);
      socket.onerror = () => setNotice("Live stream unavailable; retrying MT5 connection");
      socket.onclose = () => { if (!stopped) retryTimer = window.setTimeout(connect, 1500); };
    };
    connect();
    return () => { stopped = true; if (retryTimer !== undefined) window.clearTimeout(retryTimer); socket?.close(); };
  }, [symbol]);

  const availableSymbols = useMemo(() => {
    const matching = watchlist.map((wanted) => symbols.find((item) => item.logical_symbol === wanted || item.broker_symbol.startsWith(wanted))).filter(Boolean) as BrokerSymbol[];
    return matching.length ? matching : symbols.filter((item) => item.visible).slice(0, 8);
  }, [symbols]);
  const selectSymbol = (nextSymbol: string) => { setSymbol(nextSymbol); setSection("dashboard"); };
  const title = { dashboard: "Command Center", markets: "Market Scanner", analysis: "AI Market Analysis", execution: "Live Automation" }[section];

  return <main className="terminal-shell">
    <Sidebar section={section} setSection={setSection} status={status} />
    <section className="terminal-content">
      <header className="terminal-header"><div><span className="terminal-overline">PACBOT / MARKET INTELLIGENCE</span><h1>{title}</h1><p className="header-subtitle">Live prices, technical evidence, account exposure, and open risk in one view.</p></div><div className="header-state"><span className="stream-indicator"><i /> {status?.connected ? "LIVE STREAM" : "NO FEED"}</span><span className="utc-clock">UTC {new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false })}</span></div></header>
      {notice ? <div className="terminal-alert">{notice}</div> : null}
      {section === "dashboard" && <SignalControlPanel horizon={horizon} setHorizon={setHorizon} capabilities={capabilities} account={account} setSection={setSection} />}
      {section === "dashboard" && <DashboardView symbol={symbol} timeframe={timeframe} setTimeframe={setTimeframe} quote={quote} candles={candles} analysis={analysis} account={account} availableSymbols={availableSymbols} selectSymbol={selectSymbol} setSection={setSection} />}
      {section === "markets" && <MarketsView symbols={symbols} selected={symbol} selectSymbol={selectSymbol} />}
      {section === "analysis" && <AnalysisView symbol={symbol} analysis={analysis} setSection={setSection} />}
      {section === "execution" && account?.trade_mode === "demo" && <DemoAutomationPanel symbol={symbol} account={account} capabilities={capabilities} />}
      {section === "execution" && account?.trade_mode !== "demo" && <LiveAutomationPanel symbol={symbol} account={account} capabilities={capabilities} />}
    </section>
  </main>;
}

function Sidebar({ section, setSection, status }: { section: Section; setSection: (section: Section) => void; status?: Mt5Status }) {
  const items: Array<[Section, string, string]> = [["dashboard", "â–¦", "Dashboard"], ["markets", "â—«", "Markets"], ["analysis", "âŒ", "AI Analysis"], ["execution", "â†—", "Execution"]];
  return <aside className="terminal-nav"><div className="terminal-brand"><span className="brand-mark">P</span><div><strong>PACBOT</strong><small>TRADING DASHBOARD</small></div></div><div className="nav-group"><small>WORKSPACE</small>{items.map(([key, icon, label]) => <button key={key} className={section === key ? "terminal-nav-item selected" : "terminal-nav-item"} onClick={() => setSection(key)}><span>{icon}</span>{label}</button>)}</div><div className="nav-footer"><div className={status?.connected ? "connection good" : "connection bad"}><i />{status?.connected ? "MT5 CONNECTED" : "MT5 DISCONNECTED"}</div><small>{status?.terminal_version ? `Terminal ${status.terminal_version}` : "Read-only research mode"}</small></div></aside>;
}

function SignalControlPanel({ horizon, setHorizon, capabilities, account, setSection }: { horizon: SignalHorizon; setHorizon: (value: SignalHorizon) => void; capabilities?: Capabilities; account?: Mt5Account; setSection: (section: Section) => void }) {
  const executionReady = Boolean(capabilities?.live_trading_available && account?.connected && account.account_available && account.trade_mode === "real" && account.trading_allowed);
  return <div className="signal-controls"><div><span className="panel-label">SIGNAL HORIZON</span><div className="horizon-tabs"><button className={horizon === "short" ? "active" : ""} onClick={() => setHorizon("short")}>SHORT TERM <small>M5 · M15 · H1</small></button><button className={horizon === "long" ? "active" : ""} onClick={() => setHorizon("long")}>LONG TERM <small>H1 · H4 · D1</small></button></div></div><div className={executionReady ? "auto-trade-control ready" : "auto-trade-control"}><span className="locked-dot" />{executionReady ? "LIVE EXECUTION READY" : "LIVE EXECUTION LOCKED"}<button onClick={() => setSection("execution")}>OPEN CONTROLS</button></div></div>;
}

function DashboardView({ symbol, timeframe, setTimeframe, quote, candles, analysis, account, availableSymbols, selectSymbol, setSection }: { symbol: string; timeframe: string; setTimeframe: (value: string) => void; quote?: MarketQuote; candles?: CandleSeries; analysis?: AnalysisCandidate; account?: Mt5Account; availableSymbols: BrokerSymbol[]; selectSymbol: (symbol: string) => void; setSection: (section: Section) => void }) {
  return <>
    <div className="quote-bar">
      <div className="symbol-select"><span>INSTRUMENT</span><select value={symbol} onChange={(event) => selectSymbol(event.target.value)}>{availableSymbols.map((item) => <option key={item.broker_symbol}>{item.broker_symbol}</option>)}</select></div>
      <QuoteMetric label="BID" value={number(quote?.bid, quote?.digits ?? 5)} tone="buy" />
      <QuoteMetric label="ASK" value={number(quote?.ask, quote?.digits ?? 5)} tone="sell" />
      <QuoteMetric label="SPREAD" value={number(quote?.spread, quote?.digits ?? 5)} />
      <QuoteMetric label="MARKET" value={quote?.market_status?.toUpperCase() ?? "NO FEED"} tone={quote?.market_status === "open" ? "buy" : "muted"} />
    </div>
    <div className="account-ribbon">
      <Metric label="BALANCE" value={number(account?.balance)} />
      <Metric label="EQUITY" value={number(account?.equity)} accent />
      <Metric label="MARGIN" value={number(account?.margin)} />
      <Metric label="FREE MARGIN" value={number(account?.margin_free)} />
      <Metric label="MARGIN LEVEL" value={account?.margin_level ? `${number(account.margin_level)}%` : "--"} />
      <Metric label="TRADING" value={account?.trading_allowed ? "ENABLED" : "READ ONLY"} />
    </div>
    <div className="dashboard-grid">
      <section className="chart-panel panel-dark">
        <div className="panel-heading">
          <div><span className="panel-label">PRICE ACTION / COMPLETED CANDLES</span><h2>{symbol} <em>{timeframe}</em></h2></div>
          <div className="timeframe-tabs">{timeframes.map((item) => <button key={item} className={timeframe === item ? "active" : ""} onClick={() => setTimeframe(item)}>{item}</button>)}</div>
        </div>
        <PriceMovementChart series={candles} />
      </section>
      <InsightPanel analysis={analysis} setSection={setSection} />
      <section className="scanner-panel panel-dark">
        <PanelHeading label="MULTI-ASSET SCANNER" title="Watchlist" action="VIEW ALL" onAction={() => setSection("markets")} />
        <div className="scanner-head"><span>SYMBOL</span><span>BID / ASK</span><span>SPREAD</span><span>STATE</span></div>
        {availableSymbols.slice(0, 6).map((item) => <ScannerRow key={item.broker_symbol} item={item} selected={item.broker_symbol === symbol} onSelect={selectSymbol} />)}
      </section>
      <section className="context-panel panel-dark">
        <PanelHeading label="MARKET CONTEXT" title="Structure & signals" />
        <div className="context-grid">{["TREND", "STRUCTURE", "LIQUIDITY", "SUPPORT / RESISTANCE", "RSI / EMA", "MACD / ATR"].map((label, index) => <div key={label}><span>{label}</span><strong>{contextValue(analysis, index)}</strong></div>)}</div>
        <button className="context-action" onClick={() => setSection("analysis")}>OPEN FULL SIGNAL EVIDENCE</button>
      </section>
      <section className="positions-panel panel-dark">
        <PanelHeading label="ACCOUNT MONITOR" title="Open positions & orders" />
        <PositionTable positions={account?.positions ?? []} orders={account?.orders ?? []} />
      </section>
    </div>
  </>;
}

function MarketsView({ symbols, selected, selectSymbol }: { symbols: BrokerSymbol[]; selected: string; selectSymbol: (symbol: string) => void }) { const visible = symbols.filter((item) => item.visible); return <section className="page-stack"><div className="page-intro"><span className="terminal-overline">LIVE UNIVERSE</span><h2>Scan the broker catalog</h2><p>Inspect available instruments and choose a symbol to load its completed candles and analysis workspace.</p></div><div className="market-grid">{(visible.length ? visible : [{ broker_symbol: selected, logical_symbol: null, visible: true, selected: false, path: null, trade_mode: null }]).map((item) => <MarketCard key={item.broker_symbol} item={item} selected={item.broker_symbol === selected} onSelect={selectSymbol} />)}</div></section>; }
function MarketCard({ item, selected, onSelect }: { item: BrokerSymbol; selected: boolean; onSelect: (symbol: string) => void }) { const [quote, setQuote] = useState<MarketQuote>(); useEffect(() => { let active = true; const refresh = () => getMarketQuote(item.broker_symbol).then((value) => active && setQuote(value)).catch(() => undefined); refresh(); const timer = window.setInterval(refresh, 5000); return () => { active = false; window.clearInterval(timer); }; }, [item.broker_symbol]); return <button className={selected ? "market-card selected" : "market-card"} onClick={() => onSelect(item.broker_symbol)}><span className="market-card-top"><b>{item.logical_symbol ?? item.broker_symbol}</b><i>{quote?.market_status?.toUpperCase() ?? "WAITING"}</i></span><strong>{number(quote?.bid, quote?.digits ?? 5)}</strong><span className="market-ask">ASK {number(quote?.ask, quote?.digits ?? 5)}</span><span className="market-card-foot">{item.broker_symbol} <b>SPREAD {number(quote?.spread, quote?.digits ?? 5)}</b></span></button>; }

function AnalysisView({ symbol, analysis, setSection }: { symbol: string; analysis?: AnalysisCandidate; setSection: (section: Section) => void }) { return <section className="page-stack"><div className="analysis-hero"><div><span className="terminal-overline">EXPLAINABLE SIGNAL ENGINE</span><h2>{symbol} analysis brief</h2><p>Signals are calculated from completed candles and remain separate from execution.</p></div><span className={`signal-pill large ${analysis?.decision ?? "wait"}`}>{analysis?.decision?.replace("no_trade", "WAIT").toUpperCase() ?? "WAITING"}</span></div><div className="analysis-grid"><section className="panel-dark analysis-summary"><span className="panel-label">CURRENT READ</span><strong>{analysis?.confidence ?? "Awaiting verified data"}</strong><p>{analysis?.reasons?.join(" ") ?? "Select a connected MT5 instrument from Markets to generate an auditable analysis."}</p><div className="analysis-actions"><button onClick={() => setSection("dashboard")}>OPEN CHART â†—</button><span>{analysis?.data_source === "mt5" ? "MT5 VERIFIED" : "NO LIVE SOURCE"}</span></div></section><section className="panel-dark"><PanelHeading label="TIMEFRAME ALIGNMENT" title="Evidence by horizon" />{(analysis?.timeframe_analyses ?? []).map((item) => <div className="timeframe-row" key={item.timeframe}><b>{item.timeframe}</b><span className={`trend-${item.trend}`}>{item.trend.toUpperCase()}</span><span>{item.structure}</span><small>{item.reasons[0] ?? "No additional context"}</small></div>)}</section><section className="panel-dark"><PanelHeading label="TRADE PLAN" title="Levels and constraints" />{analysis?.trade_plan ? <div className="plan-grid">{[["ACTION", analysis.trade_plan.action], ["ENTRY", number(analysis.trade_plan.entry, 5)], ["STOP LOSS", number(analysis.trade_plan.stop_loss, 5)], ["TAKE PROFIT", number(analysis.trade_plan.take_profit, 5)], ["RISK / REWARD", analysis.trade_plan.risk_reward ?? "--"]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div> : <div className="empty-state">Trade levels withheld until the MT5 feed is verified.</div>}</section></div></section>; }

function ExecutionView({ symbol, account }: { symbol: string; account?: Mt5Account }) { const [paper, setPaper] = useState<PaperAccount>(); const [side, setSide] = useState<"buy" | "sell">("buy"); const [quantity, setQuantity] = useState("1"); const [message, setMessage] = useState(""); useEffect(() => { getPaperAccount().then(setPaper).catch(() => setMessage("Paper account unavailable")); }, []); const submit = () => createPaperOrder(symbol, side, Number(quantity)).then(setPaper).then(() => setMessage("Paper order recorded")).catch(() => setMessage("Paper order rejected")); const closeAll = () => closePaperOrders().then(setPaper).then(() => setMessage("All paper orders closed")); const reset = () => resetPaperAccount().then(setPaper).then(() => setMessage("Paper account reset")); return <section className="page-stack"><div className="page-intro"><span className="terminal-overline">CONTROLLED PRACTICE</span><h2>Paper execution desk</h2><p>Test order flow without sending anything to MT5. Live broker execution remains disabled by design.</p></div><div className="execution-grid"><section className="panel-dark execution-card"><PanelHeading label="NEW PAPER ORDER" title={symbol} /><div className="segmented"><button className={side === "buy" ? "active buy" : ""} onClick={() => setSide("buy")}>BUY</button><button className={side === "sell" ? "active sell" : ""} onClick={() => setSide("sell")}>SELL</button></div><label>QUANTITY<input type="number" min="0.01" step="0.01" value={quantity} onChange={(event) => setQuantity(event.target.value)} /></label><button className="primary-action" onClick={submit}>RECORD PAPER ORDER</button>{message && <div className="form-message">{message}</div>}<div className="safety-note"><span>â—</span> PAPER MODE ONLY<br /><small>Orders never reach your broker.</small></div></section><section className="panel-dark account-card"><PanelHeading label="SIMULATED ACCOUNT" title="Performance" /><div className="paper-metrics"><Metric label="EQUITY" value={number(paper?.equity)} accent /><Metric label="CASH" value={number(paper?.cash)} /><Metric label="TOTAL P&L" value={number(paper?.total_pnl)} accent={Boolean(paper?.total_pnl && paper.total_pnl >= 0)} /></div><div className="execution-actions"><button onClick={closeAll}>CLOSE ALL</button><button onClick={reset}>RESET ACCOUNT</button></div><p className="disclaimer">Broker account: {account?.account_id_masked ?? "not connected"}. The paper ledger is isolated from MT5.</p></section></div><section className="panel-dark journal-panel"><PanelHeading label="PAPER JOURNAL" title="Order history" />{paper?.open_orders?.length || paper?.closed_orders?.length ? <div className="journal-table">{[...(paper.open_orders ?? []), ...(paper.closed_orders ?? [])].map((order) => <div className="journal-row" key={order.id}><b>{order.symbol}</b><span className={order.side === "buy" ? "online" : "danger"}>{order.side.toUpperCase()}</span><span>{order.quantity}</span><span>{number(order.entry_price, 5)}</span><span className={order.status === "open" ? "gold" : "muted"}>{order.status.toUpperCase()}</span></div>)}</div> : <div className="empty-state">No paper orders yet. Record a small practice order to start the journal.</div>}</section></section>; }

function LiveAutomationPanel({ symbol, account, capabilities }: { symbol: string; account?: Mt5Account; capabilities?: Capabilities }) {
  const [status, setStatus] = useState<LiveAutoTradeStatus>({ running: false, status: "disarmed" });
  const [tradeMode, setTradeMode] = useState<"manual" | "automatic">("manual");
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [riskPercent, setRiskPercent] = useState("0.25");
  const [intervalSeconds, setIntervalSeconds] = useState("60");
  const [symbolsInput, setSymbolsInput] = useState(symbol);
  const [confirmation, setConfirmation] = useState("");
  const [manualSide, setManualSide] = useState<"buy" | "sell">("buy");
  const [manualVolume, setManualVolume] = useState("0.01");
  const [manualRiskPercent, setManualRiskPercent] = useState("0.25");
  const [manualEntry, setManualEntry] = useState("");
  const [manualStopLoss, setManualStopLoss] = useState("");
  const [manualTakeProfit, setManualTakeProfit] = useState("");
  const [manualSignal, setManualSignal] = useState<AnalysisCandidate>();
  const [isSignalLoading, setIsSignalLoading] = useState(false);
  const [message, setMessage] = useState("");
  const confirmationPhrase = "I_UNDERSTAND_LIVE_TRADING";

  useEffect(() => { getLiveAutoTradeStatus().then(setStatus).catch(() => undefined); }, []);
  useEffect(() => setSymbolsInput(symbol), [symbol]);
  useEffect(() => {
    setManualSignal(undefined);
    setManualEntry("");
    setManualStopLoss("");
    setManualTakeProfit("");
    setMessage("");
  }, [symbol]);
  useEffect(() => {
    const timer = window.setInterval(() => getLiveAutoTradeStatus().then(setStatus).catch(() => undefined), 2000);
    return () => window.clearInterval(timer);
  }, []);

  const targetSymbols = [...new Set(symbolsInput.split(",").map((item) => item.trim()).filter(Boolean))];
  const accountIsReal = account?.connected && account.account_available && account.trade_mode === "real" && account.trading_allowed;
  const canStart = capabilities?.live_trading_available && accountIsReal && !status.running &&
    targetSymbols.length > 0 && targetSymbols.length <= 5 && confirmation === confirmationPhrase &&
    Number(riskPercent) > 0 && Number(riskPercent) <= 0.5 && Number(intervalSeconds) >= 30 && Number(intervalSeconds) <= 3600;
  const start = () => startLiveAutoTrade(targetSymbols, Number(riskPercent), Number(intervalSeconds), confirmation)
    .then(setStatus).then(() => setMessage("Live automation armed. Monitor the account and use Stop to disarm."))
    .catch((error: Error) => setMessage(error.message));
  const stop = () => stopLiveAutoTrade().then(setStatus).then(() => setMessage("Stop requested; the current evaluation will finish safely."))
    .catch((error: Error) => setMessage(error.message));
  const evaluateAndTrade = () => {
    setIsEvaluating(true);
    setMessage("");
    analyseAndTradeLive(symbol, Number(riskPercent), confirmation)
      .then((result) => setMessage(result.executed
        ? `EA submitted ${result.side?.toUpperCase()} ${result.volume} lots on ${result.symbol}; SL ${result.stop_loss}, TP ${result.take_profit}.`
        : result.reason ?? "EA evaluated the market; no live order was submitted."))
      .catch((error: Error) => setMessage(error.message))
      .finally(() => setIsEvaluating(false));
  };
  const canPromptEa = capabilities?.live_trading_available && accountIsReal && !status.running && !isEvaluating &&
    confirmation === confirmationPhrase && Number(riskPercent) > 0 && Number(riskPercent) <= 0.5;
  const requestManualSignal = () => {
    setIsSignalLoading(true);
    setMessage("");
    getAnalysis(symbol)
      .then((signal) => {
        setManualSignal(signal);
        const plan = signal.trade_plan;
        if (signal.decision === "no_trade" || plan?.entry == null || plan.stop_loss == null || plan.take_profit == null) {
          setMessage(`No actionable signal: ${signal.reasons.join(" ")}`);
          return;
        }
        setManualSide(signal.decision);
        setManualEntry(String(plan.entry));
        setManualStopLoss(String(plan.stop_loss));
        setManualTakeProfit(String(plan.take_profit));
        setMessage("Signal ready for review. No order has been placed.");
      })
      .catch((error: Error) => setMessage(error.message))
      .finally(() => setIsSignalLoading(false));
  };
  const placeManual = () => {
    const volume = Number(manualVolume);
    const entry = Number(manualEntry);
    const stopLoss = Number(manualStopLoss);
    const takeProfit = Number(manualTakeProfit);
    if (!Number.isFinite(volume) || volume <= 0 || !Number.isFinite(entry) || !Number.isFinite(stopLoss) || !Number.isFinite(takeProfit)) {
      setMessage("Manual live trade requires valid volume, entry, stop loss, and take profit.");
      return;
    }
    manualLiveTrade(symbol, manualSide, volume, Number(manualRiskPercent), entry, stopLoss, takeProfit, confirmation)
      .then((result) => setMessage(result.executed ? `Manual ${result.side?.toUpperCase()} order submitted: ${result.volume} lots.` : result.reason ?? "No manual live order submitted."))
      .catch((error: Error) => setMessage(error.message));
  };

  return <section className="panel-dark auto-panel live-auto-panel">
    <PanelHeading label="MT5 REAL-ACCOUNT AUTOMATION" title={status.running ? `Armed · ${status.symbols?.join(", ")}` : "Account-aware signal runner"} />
    <div className="live-account-strip">
      <Metric label="ACCOUNT MODE" value={account?.trade_mode?.toUpperCase() ?? "UNKNOWN"} />
      <Metric label="BALANCE" value={`${number(account?.balance)} ${account?.currency ?? ""}`} />
      <Metric label="EQUITY" value={`${number(account?.equity)} ${account?.currency ?? ""}`} accent />
      <Metric label="OPEN POSITIONS" value={String(account?.positions.length ?? 0)} />
      <Metric label="FREE MARGIN" value={`${number(account?.margin_free)} ${account?.currency ?? ""}`} />
    </div>
    <div className="live-safety-banner">
      <strong>{accountIsReal && capabilities?.live_trading_available ? "REAL ACCOUNT READY" : "LIVE EXECUTION LOCKED"}</strong>
      <span>Every entry is sized from current equity and broker tick values, includes SL/TP, and is blocked by configured exposure, position, order, and session-loss limits.</span>
    </div>
    <div className="segmented">
      <button className={tradeMode === "manual" ? "active" : ""} onClick={() => setTradeMode("manual")}>MANUAL SIGNAL</button>
      <button className={tradeMode === "automatic" ? "active" : ""} onClick={() => setTradeMode("automatic")}>AUTOMATIC MANAGED</button>
    </div>
    {tradeMode === "manual" ? (
      <div className="auto-form live-auto-form">
        <button className="primary-action" disabled={!account?.connected || isSignalLoading || status.running} onClick={requestManualSignal}>
          {isSignalLoading ? "GENERATING SIGNAL..." : "GENERATE BOT SIGNAL"}
        </button>
        {manualSignal?.trade_plan && <div className="levels">
          <div><span>SIGNAL</span><strong>{manualSignal.decision.toUpperCase()} · {manualSignal.confidence}</strong></div>
          <div><span>ENTRY</span><strong>{number(manualSignal.trade_plan.entry, 5)}</strong></div>
          <div><span>STOP LOSS</span><strong>{number(manualSignal.trade_plan.stop_loss, 5)}</strong></div>
          <div><span>TAKE PROFIT</span><strong>{number(manualSignal.trade_plan.take_profit, 5)}</strong></div>
        </div>}
        <div className="segmented">
          <button className={manualSide === "buy" ? "active buy" : ""} onClick={() => setManualSide("buy")}>BUY</button>
          <button className={manualSide === "sell" ? "active sell" : ""} onClick={() => setManualSide("sell")}>SELL</button>
        </div>
        <label>VOLUME<input type="number" min="0.01" max="10" step="0.01" value={manualVolume} onChange={(event) => setManualVolume(event.target.value)} /></label>
        <label>MAX RISK PER TRADE (%)<input type="number" min="0.01" max="0.25" step="0.01" value={manualRiskPercent} onChange={(event) => setManualRiskPercent(event.target.value)} /></label>
        <label>ENTRY<input type="number" min="0" step="0.0001" value={manualEntry} onChange={(event) => setManualEntry(event.target.value)} placeholder="1.1000" /></label>
        <label>STOP LOSS<input type="number" min="0" step="0.0001" value={manualStopLoss} onChange={(event) => setManualStopLoss(event.target.value)} placeholder="1.0950" /></label>
        <label>TAKE PROFIT<input type="number" min="0" step="0.0001" value={manualTakeProfit} onChange={(event) => setManualTakeProfit(event.target.value)} placeholder="1.1200" /></label>
        <label>LIVE ACKNOWLEDGEMENT<input value={confirmation} onChange={(event) => setConfirmation(event.target.value)} placeholder={confirmationPhrase} autoComplete="off" /></label>
        <button className="primary-action" disabled={!accountIsReal || confirmation !== confirmationPhrase || status.running} onClick={placeManual}>PLACE MANUAL LIVE ORDER</button>
      </div>
    ) : (
      <div className="auto-form live-auto-form">
        <p className="disclaimer">Automatic mode manages signal checks and order entry with broker-side stop loss and take profit. A one-shot EA action may place a real order.</p>
        <label>TARGET BROKER SYMBOLS<input value={symbolsInput} onChange={(event) => setSymbolsInput(event.target.value)} placeholder="EURUSD, XAUUSD" /></label>
        <label>RISK PER ORDER (%)<input type="number" min="0.01" max="0.25" step="0.01" value={riskPercent} onChange={(event) => setRiskPercent(event.target.value)} /></label>
        <label>CHECK INTERVAL (SEC)<input type="number" min="30" max="3600" step="30" value={intervalSeconds} onChange={(event) => setIntervalSeconds(event.target.value)} /></label>
        <label>LIVE ACKNOWLEDGEMENT<input value={confirmation} onChange={(event) => setConfirmation(event.target.value)} placeholder={confirmationPhrase} autoComplete="off" /></label>
        <button className="primary-action" disabled={!canPromptEa} onClick={evaluateAndTrade}>
          {isEvaluating ? "EA EVALUATING..." : "PROMPT EA: EVALUATE & TRADE NOW"}
        </button>
        {status.running
          ? <button className="danger-action" onClick={stop}>STOP LIVE AUTOMATION</button>
          : <button className="primary-action" disabled={!canStart} onClick={start}>ARM LIVE AUTOMATION</button>}
      </div>
    )}
    <div className="auto-status"><strong>{status.status.toUpperCase()}</strong><span>{status.evaluations ?? 0} evaluations</span><span>{status.orders_submitted ?? 0} orders submitted</span><span>Start equity {number(status.starting_equity)} {account?.currency ?? ""}</span><span>{account?.trading_allowed ? "BROKER TRADING ENABLED" : "BROKER TRADING DISABLED"}</span></div>
    {status.last_result && <p className="disclaimer">Latest evaluation: {status.last_result.reason ?? (status.last_result.executed ? `${status.last_result.side?.toUpperCase()} ${status.last_result.volume} lots on ${status.last_result.symbol}; risk ${number(status.last_result.risk_amount)} ${account?.currency ?? ""}` : "No order submitted")}</p>}
    {message && <p className="form-message">{message}</p>}
    <p className="disclaimer live-disclaimer">Signals use deterministic multi-timeframe technical rules, not a self-learning or profit-guaranteeing AI. Live markets can lose money rapidly. This run ends after its order limit or any risk/account guard; it does not restart automatically. Default server limits: 0.25% risk per order, 0.75% aggregate open risk, 3 concurrent positions, 3 submitted orders, and 1% session equity drawdown. Live settings must also be enabled by the operator in the local environment.</p>
  </section>;
}

function DemoAutomationPanel({ symbol, account, capabilities }: { symbol: string; account?: Mt5Account; capabilities?: Capabilities }) {
  const [status, setStatus] = useState<DemoAutoTradeStatus>({ running: false, status: "stopped" });
  const [tradeMode, setTradeMode] = useState<"manual" | "automatic">("manual");
  const [riskPercent, setRiskPercent] = useState("0.25");
  const [intervalSeconds, setIntervalSeconds] = useState("60");
  const [maxOrders, setMaxOrders] = useState("1");
  const [symbolsInput, setSymbolsInput] = useState(symbol);
  const [manualSide, setManualSide] = useState<"buy" | "sell">("buy");
  const [manualVolume, setManualVolume] = useState("0.01");
  const [manualEntry, setManualEntry] = useState("");
  const [manualStopLoss, setManualStopLoss] = useState("");
  const [manualTakeProfit, setManualTakeProfit] = useState("");
  const [manualSignal, setManualSignal] = useState<AnalysisCandidate>();
  const [isSignalLoading, setIsSignalLoading] = useState(false);
  const [message, setMessage] = useState("");
  useEffect(() => { getDemoAutoTradeStatus().then(setStatus).catch(() => undefined); }, []);
  useEffect(() => {
    setManualSignal(undefined);
    setManualEntry("");
    setManualStopLoss("");
    setManualTakeProfit("");
    setMessage("");
  }, [symbol]);
  useEffect(() => {
    const timer = window.setInterval(() => getDemoAutoTradeStatus().then(setStatus).catch(() => undefined), 2000);
    return () => window.clearInterval(timer);
  }, []);
  const targetSymbols = [...new Set(symbolsInput.split(",").map((item) => item.trim()).filter(Boolean))];
  const activeSymbols = new Set([...(account?.positions.map((position) => position.symbol) ?? []), ...(account?.orders.map((order) => order.symbol) ?? [])]);
  const accountCanTrade = capabilities?.demo_execution_available && account?.connected && account.account_available && account.trade_mode === "demo" && account.trading_allowed;
  const selectedSymbolAlreadyActive = activeSymbols.has(symbol);
  const canStart = accountCanTrade && !status.running && targetSymbols.length > 0 && targetSymbols.length <= 5 && targetSymbols.some((item) => !activeSymbols.has(item));
  const canOneClick = accountCanTrade && !status.running && !selectedSymbolAlreadyActive;
  const start = () => startDemoAutoTrade(targetSymbols, Number(riskPercent), Number(intervalSeconds), Number(maxOrders)).then(setStatus).then(() => setMessage(`Demo automation started for ${targetSymbols.length} symbol(s), capped at ${maxOrders} orders and 10 checks.`)).catch((error: Error) => setMessage(error.message));
  const placeOne = () => oneClickDemoTrade(symbol, Number(riskPercent)).then((result) => setMessage(result.executed ? `Demo ${result.side?.toUpperCase()} order submitted: ${result.volume} lots.` : result.reason ?? "No order submitted.")).catch((error: Error) => setMessage(error.message));
  const requestManualSignal = () => {
    setIsSignalLoading(true);
    setMessage("");
    getAnalysis(symbol)
      .then((signal) => {
        setManualSignal(signal);
        const plan = signal.trade_plan;
        if (signal.decision === "no_trade" || plan?.entry == null || plan.stop_loss == null || plan.take_profit == null) {
          setMessage(`No actionable signal: ${signal.reasons.join(" ")}`);
          return;
        }
        setManualSide(signal.decision);
        setManualEntry(String(plan.entry));
        setManualStopLoss(String(plan.stop_loss));
        setManualTakeProfit(String(plan.take_profit));
        setMessage("Signal ready for review. No order has been placed.");
      })
      .catch((error: Error) => setMessage(error.message))
      .finally(() => setIsSignalLoading(false));
  };
  const placeManual = () => {
    const volume = Number(manualVolume);
    const entry = Number(manualEntry);
    const stopLoss = Number(manualStopLoss);
    const takeProfit = Number(manualTakeProfit);
    if (!Number.isFinite(volume) || volume <= 0 || !Number.isFinite(entry) || !Number.isFinite(stopLoss) || !Number.isFinite(takeProfit)) {
      setMessage("Manual trade requires valid volume, entry, stop loss, and take profit.");
      return;
    }
    manualDemoTrade(symbol, manualSide, volume, entry, stopLoss, takeProfit)
      .then((result) => setMessage(result.executed ? `Manual ${result.side?.toUpperCase()} order submitted: ${result.volume} lots.` : result.reason ?? "No manual order submitted."))
      .catch((error: Error) => setMessage(error.message));
  };
  const stop = () => stopDemoAutoTrade().then(setStatus).then(() => setMessage("Stop requested."));
  return <section className="panel-dark auto-panel">
    <PanelHeading label="MT5 DEMO AUTOMATION" title={status.running ? `Running · ${status.symbol}` : "Trade mode selector"} />
    <div className="live-safety-banner">
      <strong>{accountCanTrade ? "DEMO EXECUTION READY" : "DEMO EXECUTION LOCKED"}</strong>
      <span>{accountCanTrade ? "Connected demo-account orders only. Live-account orders are not enabled by this panel." : "Connect an MT5 demo account and set DEMO_EXECUTION_ENABLED=true with TRADING_MODE=demo in .env."}</span>
    </div>
    <div className="segmented">
      <button className={tradeMode === "manual" ? "active" : ""} onClick={() => setTradeMode("manual")}>MANUAL SIGNAL</button>
      <button className={tradeMode === "automatic" ? "active" : ""} onClick={() => setTradeMode("automatic")}>AUTOMATIC MANAGED</button>
    </div>
    {tradeMode === "manual" ? (
      <div className="auto-form">
        <button className="primary-action" disabled={!account?.connected || isSignalLoading || status.running} onClick={requestManualSignal}>
          {isSignalLoading ? "GENERATING SIGNAL..." : "GENERATE BOT SIGNAL"}
        </button>
        {manualSignal?.trade_plan && <div className="levels">
          <div><span>SIGNAL</span><strong>{manualSignal.decision.toUpperCase()} · {manualSignal.confidence}</strong></div>
          <div><span>ENTRY</span><strong>{number(manualSignal.trade_plan.entry, 5)}</strong></div>
          <div><span>STOP LOSS</span><strong>{number(manualSignal.trade_plan.stop_loss, 5)}</strong></div>
          <div><span>TAKE PROFIT</span><strong>{number(manualSignal.trade_plan.take_profit, 5)}</strong></div>
        </div>}
        <div className="segmented">
          <button className={manualSide === "buy" ? "active buy" : ""} onClick={() => setManualSide("buy")}>BUY</button>
          <button className={manualSide === "sell" ? "active sell" : ""} onClick={() => setManualSide("sell")}>SELL</button>
        </div>
        <label>VOLUME<input type="number" min="0.01" max="10" step="0.01" value={manualVolume} onChange={(event) => setManualVolume(event.target.value)} /></label>
        <label>ENTRY<input type="number" min="0" step="0.0001" value={manualEntry} onChange={(event) => setManualEntry(event.target.value)} placeholder="1.1000" /></label>
        <label>STOP LOSS<input type="number" min="0" step="0.0001" value={manualStopLoss} onChange={(event) => setManualStopLoss(event.target.value)} placeholder="1.0950" /></label>
        <label>TAKE PROFIT<input type="number" min="0" step="0.0001" value={manualTakeProfit} onChange={(event) => setManualTakeProfit(event.target.value)} placeholder="1.1200" /></label>
        <button className="primary-action" disabled={!accountCanTrade} onClick={placeManual}>PLACE MANUAL DEMO ORDER</button>
      </div>
    ) : (
      <div className="auto-form">
        <p className="disclaimer">Automatic mode manages signal checks and order entry with broker-side stop loss and take profit.</p>
        <label>TARGET SYMBOLS<input value={symbolsInput} onChange={(event) => setSymbolsInput(event.target.value)} placeholder="EURUSD, XAUUSD" /></label>
        <label>RISK / ORDER (%)<input type="number" min="0.01" max="0.25" step="0.01" value={riskPercent} onChange={(event) => setRiskPercent(event.target.value)} /></label>
        <label>CHECK INTERVAL (SEC)<input type="number" min="30" max="3600" step="30" value={intervalSeconds} onChange={(event) => setIntervalSeconds(event.target.value)} /></label>
        <label>MAX ORDERS<select value={maxOrders} onChange={(event) => setMaxOrders(event.target.value)}><option value="1">1 order</option><option value="2">2 orders</option><option value="3">3 orders</option></select></label>
        <button className="primary-action" disabled={!canOneClick || Number(riskPercent) <= 0 || Number(riskPercent) > 0.25} onClick={placeOne}>PLACE ONE DEMO ORDER</button>
        {status.running ? <button className="danger-action" onClick={stop}>STOP AUTOMATION</button> : <button className="primary-action" disabled={!canStart || Number(riskPercent) <= 0 || Number(riskPercent) > 0.25 || Number(intervalSeconds) < 30 || Number(intervalSeconds) > 3600} onClick={start}>START DEMO AUTOMATION</button>}
      </div>
    )}
    <div className="auto-status"><strong>{status.status.toUpperCase()}</strong><span>{status.evaluations ?? 0} checks</span><span>{status.orders_submitted ?? 0} orders submitted</span><span>{account?.trade_mode?.toUpperCase() ?? "ACCOUNT UNKNOWN"} · {account?.trading_allowed ? "TRADING ALLOWED" : "TRADING BLOCKED"}</span>{selectedSymbolAlreadyActive && <span>{symbol} HAS AN OPEN POSITION / ORDER</span>}</div>
    {status.last_result && <p className="disclaimer">Last result: {status.last_result.reason ?? (status.last_result.executed ? `${status.last_result.side?.toUpperCase()} ${status.last_result.volume} lots` : "No order submitted")}</p>}
    {message && <p className="form-message">{message}</p>}
    <p className="disclaimer">Manual trade lets the user set entry, stop loss, and take profit. Automatic trade uses risk-based sizing and periodic checks. Demo account only. One existing position/order blocks another entry on that symbol. Maximum 0.25% risk per order and 10 total checks per run.</p>
  </section>;
}

function QuoteMetric({ label, value, tone = "" }: { label: string; value: string; tone?: string }) { return <div><span>{label}</span><strong className={tone ? `price-${tone}` : ""}>{value}</strong></div>; }
function Metric({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) { return <div><span>{label}</span><strong className={accent ? "accent" : ""}>{value}</strong></div>; }
function PanelHeading({ label, title, action, onAction }: { label: string; title: string; action?: string; onAction?: () => void }) { return <div className="panel-heading"><div><span className="panel-label">{label}</span><h2>{title}</h2></div>{action && <button className="small-action" onClick={onAction}>{action}</button>}</div>; }
function InsightPanel({ analysis, setSection }: { analysis?: AnalysisCandidate; setSection: (section: Section) => void }) { return <section className="insight-panel panel-dark"><div className="panel-heading"><div><span className="panel-label">AI TRADE SETUP</span><h2>Decision context</h2></div><span className={`signal-pill ${analysis?.decision ?? "wait"}`}>{analysis?.decision?.replace("no_trade", "WAIT").toUpperCase() ?? "WAIT"}</span></div><div className="setup-head"><strong>{analysis?.confidence ?? "Awaiting analysis"}</strong><span>confidence</span></div><p className="insight-copy">{analysis?.reasons?.[0] ?? "Connect MT5 and select an instrument to generate a setup."}</p>{analysis?.trade_plan?.entry !== null && analysis?.trade_plan ? <div className="levels">{[["ENTRY", analysis.trade_plan.entry], ["STOP LOSS", analysis.trade_plan.stop_loss], ["TAKE PROFIT", analysis.trade_plan.take_profit], ["RISK / REWARD", analysis.trade_plan.risk_reward]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{typeof value === "number" ? number(value, 5) : value ?? "--"}</strong></div>)}</div> : <div className="withheld">TRADE LEVELS WITHHELD<br /><small>Requires verified MT5 candles</small></div>}<button className="panel-link" onClick={() => setSection("analysis")}>VIEW FULL ANALYSIS â†—</button></section>; }
function contextValue(analysis: AnalysisCandidate | undefined, index: number) { const item = analysis?.timeframe_analyses?.[0]; const technical = analysis?.technical?.[0]; const structure = analysis?.market_structure?.[0]; if (!item) return "--"; return [item.trend.toUpperCase(), structure?.bos ? `${structure.bos.toUpperCase()} BOS` : item.structure, item.liquidity[0] ?? "--", `${number(item.support)} / ${number(item.resistance)}`, technical?.rsi_14 !== null && technical?.rsi_14 !== undefined ? `RSI ${number(technical.rsi_14)}` : "--", technical?.macd_histogram !== null && technical?.macd_histogram !== undefined ? `MACD ${number(technical.macd_histogram, 4)} / ATR ${number(technical.atr_14, 5)}` : "--"][index]; }
function PositionTable({ positions, orders }: { positions: Mt5Account["positions"]; orders: Mt5Account["orders"] }) { return positions.length || orders.length ? <div className="position-table">{positions.map((position) => <div className="position-row" key={`position-${position.ticket}`}><strong>{position.symbol}</strong><span className={position.side === "buy" ? "online" : "danger"}>{position.side.toUpperCase()}</span><span>{number(position.volume)}</span><span>{number(position.price_current, 5)}</span><b className={(position.profit ?? 0) >= 0 ? "online" : "danger"}>{number(position.profit)}</b></div>)}{orders.map((order) => <div className="position-row" key={`order-${order.ticket}`}><strong>{order.symbol}</strong><span className="muted">ORDER</span><span>{number(order.volume)}</span><span>{number(order.price_open, 5)}</span><b className="muted">PENDING</b></div>)}</div> : <div className="chart-empty compact">No open MT5 positions or pending orders.</div>; }
function ScannerRow({ item, selected, onSelect }: { item: BrokerSymbol; selected: boolean; onSelect: (symbol: string) => void }) { const [quote, setQuote] = useState<MarketQuote>(); useEffect(() => { const refresh = () => getMarketQuote(item.broker_symbol).then(setQuote).catch(() => undefined); refresh(); const timer = window.setInterval(refresh, 5000); return () => window.clearInterval(timer); }, [item.broker_symbol]); return <button className={selected ? "scanner-row selected" : "scanner-row"} onClick={() => onSelect(item.broker_symbol)}><strong>{item.broker_symbol}</strong><span>{number(quote?.bid, quote?.digits ?? 5)} / {number(quote?.ask, quote?.digits ?? 5)}</span><span>{number(quote?.spread, quote?.digits ?? 5)}</span><b className={quote?.quote_available ? "online" : "offline"}>{quote?.quote_available ? "LIVE" : "--"}</b></button>; }
function PriceMovementChart({ series }: { series?: CandleSeries }) {
  const [chartAnalysis, setChartAnalysis] = useState<AnalysisCandidate>();
  useEffect(() => {
    if (!series?.broker_symbol) return;
    getAnalysis(series.broker_symbol).then(setChartAnalysis).catch(() => setChartAnalysis(undefined));
  }, [series?.broker_symbol]);
  if (!series?.candles.length) return <div className="chart-empty">Awaiting completed MT5 candles...</div>;
  const candles = series.candles.slice(-70);
  const chartWidth = 900;
  const chartHeight = 320;
  const plotLeft = 54;
  const plotRight = 18;
  const plotTop = 14;
  const plotBottom = 42;
  const plotWidth = chartWidth - plotLeft - plotRight;
  const plotHeight = chartHeight - plotTop - plotBottom;
  const tradePlan = chartAnalysis?.trade_plan;
  const tradeLevels = [tradePlan?.entry, tradePlan?.stop_loss, tradePlan?.take_profit].filter((value): value is number => value !== null && value !== undefined);
  const technical = chartAnalysis?.technical?.find((item) => item.timeframe === series.timeframe);
  const structure = chartAnalysis?.market_structure?.find((item) => item.timeframe === series.timeframe);
  const timeframeAnalysis = chartAnalysis?.timeframe_analyses?.find((item) => item.timeframe === series.timeframe);
  const emaValues = candles.map((candle, index) => {
    const window = candles.slice(Math.max(0, index - 19), index + 1);
    return window.reduce((sum, item) => sum + item.close, 0) / window.length;
  });
  const structureLevels = [timeframeAnalysis?.support, timeframeAnalysis?.resistance].filter((value): value is number => value !== undefined && value !== null);
  const zoneLevels = (structure?.fvg ?? []).flatMap((zone) => [zone.low, zone.high]).concat((structure?.order_blocks ?? []).flatMap((zone) => [zone.low, zone.high]));
  const min = Math.min(...candles.map((item) => item.low), ...tradeLevels, ...structureLevels, ...zoneLevels);
  const max = Math.max(...candles.map((item) => item.high), ...tradeLevels, ...structureLevels, ...zoneLevels);
  const padding = (max - min || 1) * 0.08;
  const low = min - padding;
  const high = max + padding;
  const scale = (value: number) => plotTop + ((high - value) / (high - low)) * plotHeight;
  const step = plotWidth / candles.length;
  const candleWidth = Math.max(3, step * 0.55);
  const closePath = candles.map((candle, index) => `${index === 0 ? "M" : "L"} ${plotLeft + index * step + step / 2} ${scale(candle.close)}`).join(" ");
  const emaPath = emaValues.map((value, index) => `${index === 0 ? "M" : "L"} ${plotLeft + index * step + step / 2} ${scale(value)}`).join(" ");
  const priceTicks = Array.from({ length: 5 }, (_, index) => high - ((high - low) * index) / 4);
  const timeIndexes = [0, Math.floor((candles.length - 1) * 0.25), Math.floor((candles.length - 1) * 0.5), Math.floor((candles.length - 1) * 0.75), candles.length - 1];
  const formatTime = (value: string) => new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
  const latest = candles[candles.length - 1];
  const latestX = plotLeft + (candles.length - 1) * step + step / 2;
  return <div className="chart-wrap">
    <div className={`chart-signal ${chartAnalysis?.decision ?? "wait"}`}><strong>{chartAnalysis?.decision === "no_trade" ? "WAIT" : chartAnalysis?.decision?.toUpperCase() ?? "ANALYZING"}</strong><span>{chartAnalysis?.confidence ?? "Awaiting verified MT5 analysis"}</span></div>
    <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} role="img" aria-label={`${series.broker_symbol} ${series.timeframe} candlestick chart with price and time axes`}>
      {priceTicks.map((value, index) => <g key={value}><line x1={plotLeft} x2={chartWidth - plotRight} y1={scale(value)} y2={scale(value)} className="chart-grid-line" /><text x={plotLeft - 9} y={scale(value) + 4} textAnchor="end" className="chart-axis-label">{value.toFixed(series.timeframe === "D1" ? 2 : 3)}</text></g>)}
      <line x1={plotLeft} y1={plotTop} x2={plotLeft} y2={chartHeight - plotBottom} className="chart-axis-line" />
      <line x1={plotLeft} y1={chartHeight - plotBottom} x2={chartWidth - plotRight} y2={chartHeight - plotBottom} className="chart-axis-line" />
      {structure?.fvg.map((zone, index) => <g key={`fvg-${index}`}><rect x={plotLeft + step * Math.max(0, candles.length - 20 + index)} y={scale(zone.high)} width={step * Math.min(20, candles.length)} height={Math.max(2, scale(zone.low) - scale(zone.high))} className={`structure-zone fvg-${zone.side}`} /><text x={plotLeft + 8} y={scale(zone.high) + 12} className="structure-label">{zone.side === "bullish" ? "BULLISH FVG" : "BEARISH FVG"}</text></g>)}
      {structure?.order_blocks.map((zone, index) => <g key={`ob-${index}`}><rect x={plotLeft + step * Math.max(0, candles.length - 12)} y={scale(zone.high)} width={step * 12} height={Math.max(2, scale(zone.low) - scale(zone.high))} className={`structure-zone order-block-${zone.side}`} /><text x={plotLeft + 8} y={scale(zone.high) + 25} className="structure-label">{zone.side === "bullish" ? "BULLISH OB" : "BEARISH OB"}</text></g>)}
      {timeframeAnalysis?.support !== null && timeframeAnalysis?.support !== undefined && <g><line x1={plotLeft} x2={chartWidth - plotRight} y1={scale(timeframeAnalysis.support)} y2={scale(timeframeAnalysis.support)} className="structure-level support-line" /><text x={plotLeft + 6} y={scale(timeframeAnalysis.support) - 4} className="structure-label">SUPPORT</text></g>}
      {timeframeAnalysis?.resistance !== null && timeframeAnalysis?.resistance !== undefined && <g><line x1={plotLeft} x2={chartWidth - plotRight} y1={scale(timeframeAnalysis.resistance)} y2={scale(timeframeAnalysis.resistance)} className="structure-level resistance-line" /><text x={plotLeft + 6} y={scale(timeframeAnalysis.resistance) - 4} className="structure-label">RESISTANCE</text></g>}
      {candles.map((candle, index) => { const x = plotLeft + index * step + step / 2; const up = candle.close >= candle.open; const y = Math.min(scale(candle.open), scale(candle.close)); const height = Math.max(2, Math.abs(scale(candle.close) - scale(candle.open))); return <g key={candle.open_time}><line x1={x} x2={x} y1={scale(candle.high)} y2={scale(candle.low)} className={up ? "candle-up" : "candle-down"} /><rect x={x - candleWidth / 2} y={y} width={candleWidth} height={height} className={up ? "candle-up" : "candle-down"} /></g>; })}
      <path d={closePath} className="price-movement-line" />
      <path d={emaPath} className="ema-line" />
      {structure?.bos && <text x={latestX - 8} y={scale(latest.close) - 26} textAnchor="end" className={`structure-label ${structure.bos === "bullish" ? "bullish-label" : "bearish-label"}`}>{structure.bos.toUpperCase()} BOS</text>}
      {structure?.choch && <text x={latestX - 8} y={scale(latest.close) - 40} textAnchor="end" className="structure-label choch-label">{structure.choch.toUpperCase()} CHoCH</text>}
      {tradePlan && [["ENTRY", tradePlan.entry, "trade-entry"], ["STOP LOSS", tradePlan.stop_loss, "trade-stop"], ["TAKE PROFIT", tradePlan.take_profit, "trade-target"]].map(([label, value, className]) => typeof value === "number" && <g key={label}><line x1={plotLeft} x2={chartWidth - plotRight} y1={scale(value)} y2={scale(value)} className={`trade-level-line ${className}`} /><rect x={chartWidth - 126} y={scale(value) - 10} width="108" height="18" className={`trade-level-label ${className}`} /><text x={chartWidth - 72} y={scale(value) + 3} textAnchor="middle" className="trade-level-text">{label} {value.toFixed(series.timeframe === "D1" ? 2 : 3)}</text></g>)}
      <circle cx={latestX} cy={scale(latest.close)} r="4" className="latest-price-dot" />
      <text x={latestX} y={scale(latest.close) - 10} textAnchor="middle" className="latest-price-label">{latest.close.toFixed(series.timeframe === "D1" ? 2 : 3)}</text>
      {timeIndexes.map((index) => <text key={`${candles[index].open_time}-${index}`} x={plotLeft + index * step + step / 2} y={chartHeight - 14} textAnchor="middle" className="chart-axis-label">{formatTime(candles[index].open_time)}</text>)}
      <text x="10" y="18" className="chart-axis-title">PRICE</text><text x={chartWidth - plotRight} y={chartHeight - 1} textAnchor="end" className="chart-axis-title">UTC TIME</text>
    </svg>
    <div className="chart-legend"><span><i className="legend-line" /> CLOSE</span><span><i className="legend-ema" /> EMA 20</span><span><i className="legend-zone" /> FVG / OB</span><span>{candles.length} candles · MT5</span></div>
  </div>;
}

function LegacyPriceChart({ series }: { series?: CandleSeries }) { if (!series?.candles.length) return <div className="chart-empty">Awaiting completed MT5 candles...</div>; const candles = series.candles.slice(-70); const min = Math.min(...candles.map((item) => item.low)); const max = Math.max(...candles.map((item) => item.high)); const scale = (value: number) => 276 - ((value - min) / (max - min || 1)) * 246; const width = 900 / candles.length; return <div className="chart-wrap"><svg viewBox="0 0 900 300" role="img" aria-label={`${series.broker_symbol} ${series.timeframe} candlestick chart`}><line x1="0" y1="276" x2="900" y2="276" className="chart-axis" />{candles.map((candle, index) => { const x = index * width + width / 2; const up = candle.close >= candle.open; const y = Math.min(scale(candle.open), scale(candle.close)); const height = Math.max(2, Math.abs(scale(candle.close) - scale(candle.open))); return <g key={candle.open_time}><line x1={x} x2={x} y1={scale(candle.high)} y2={scale(candle.low)} className={up ? "candle-up" : "candle-down"} /><rect x={x - width * .27} y={y} width={width * .54} height={height} className={up ? "candle-up" : "candle-down"} /></g>; })}</svg><div className="chart-note">{candles.length} completed candles Â· UTC Â· source: MT5</div></div>; }
