from types import ModuleType, SimpleNamespace

from backend.execution.mt5_terminal import Mt5TerminalAdapter


class FakeMt5(ModuleType):
    def __init__(self, initialize_result: bool = True) -> None:
        super().__init__("MetaTrader5")
        self.initialize_result = initialize_result
        self.initialize_options: dict[str, int | str] | None = None
        self.shutdown_calls = 0
        self.order_send_calls = 0
        self.account_trade_mode = 0
        self.account_trade_allowed = True

    def initialize(self, **options: int | str) -> bool:
        self.initialize_options = options
        return self.initialize_result

    def version(self) -> tuple[int, int, int]:
        return (5, 0, 1234)

    def last_error(self) -> tuple[int, str]:
        return (-10003, "IPC initialization failed")

    def shutdown(self) -> None:
        self.shutdown_calls += 1

    def account_info(self) -> SimpleNamespace:
        return SimpleNamespace(
            login=12345678,
            trade_mode=self.account_trade_mode,
            currency="USD",
            balance=100.0,
            equity=99.5,
            margin=10.0,
            margin_free=89.5,
            margin_level=995.0,
            trade_allowed=self.account_trade_allowed,
        )

    def order_send(self, _: dict[str, object]) -> SimpleNamespace:
        self.order_send_calls += 1
        return SimpleNamespace(retcode=10009, order=123)


def test_probe_initializes_without_credentials_and_closes_connection() -> None:
    fake_mt5 = FakeMt5()
    adapter = Mt5TerminalAdapter(
        terminal_path="C:/Program Files/MetaTrader 5/terminal64.exe",
        timeout_ms=10_000,
        module_loader=lambda _: fake_mt5,
    )

    result = adapter.probe()

    assert result.connected is True
    assert result.package_available is True
    assert result.terminal_version == "5.0.1234"
    assert fake_mt5.initialize_options == {
        "path": "C:/Program Files/MetaTrader 5/terminal64.exe",
        "timeout": 10_000,
    }
    assert fake_mt5.shutdown_calls == 1


def test_probe_returns_mt5_error_and_closes_connection() -> None:
    fake_mt5 = FakeMt5(initialize_result=False)
    adapter = Mt5TerminalAdapter(
        terminal_path=None,
        timeout_ms=10_000,
        module_loader=lambda _: fake_mt5,
    )

    result = adapter.probe()

    assert result.connected is False
    assert result.package_available is True
    assert result.error_code == -10003
    assert result.error_message == "IPC initialization failed"
    assert fake_mt5.initialize_options == {"timeout": 10_000}
    assert fake_mt5.shutdown_calls == 1


def test_probe_handles_missing_package_without_attempting_shutdown() -> None:
    def missing_package(_: str) -> ModuleType:
        raise ModuleNotFoundError

    result = Mt5TerminalAdapter(
        terminal_path=None,
        timeout_ms=10_000,
        module_loader=missing_package,
    ).probe()

    assert result.connected is False
    assert result.package_available is False
    assert result.error_message == "MetaTrader5 Python package is not installed."


def test_account_snapshot_is_redacted_and_read_only() -> None:
    fake_mt5 = FakeMt5()
    adapter = Mt5TerminalAdapter(
        terminal_path=None,
        timeout_ms=10_000,
        module_loader=lambda _: fake_mt5,
    )

    snapshot = adapter.account_snapshot()

    assert snapshot.connected is True
    assert snapshot.account_available is True
    assert snapshot.account_id_masked == "***5678"
    assert snapshot.trade_mode == "demo"
    assert snapshot.currency == "USD"
    assert snapshot.balance == 100.0
    assert snapshot.equity == 99.5
    assert snapshot.margin_free == 89.5
    assert snapshot.trading_allowed is True
    assert fake_mt5.shutdown_calls == 1


def test_account_snapshot_surfaces_mt5_error_and_closes_connection() -> None:
    fake_mt5 = FakeMt5()
    fake_mt5.account_info = lambda: None  # type: ignore[method-assign]
    adapter = Mt5TerminalAdapter(
        terminal_path=None,
        timeout_ms=10_000,
        module_loader=lambda _: fake_mt5,
    )

    snapshot = adapter.account_snapshot()

    assert snapshot.connected is True
    assert snapshot.account_available is False
    assert snapshot.error_code == -10003
    assert snapshot.error_message == "IPC initialization failed"
    assert fake_mt5.shutdown_calls == 1


def test_demo_order_guard_rejects_real_account_before_order_submission() -> None:
    fake_mt5 = FakeMt5()
    fake_mt5.account_trade_mode = 2
    adapter = Mt5TerminalAdapter(None, 10_000, module_loader=lambda _: fake_mt5)

    result = adapter.send_market_order(
        "EURUSD",
        "buy",
        0.01,
        1.0,
        1.1,
        required_trade_mode="demo",
    )

    assert result.submitted is False
    assert result.error_message == "Order requires an MT5 demo account."
    assert fake_mt5.order_send_calls == 0
    assert fake_mt5.shutdown_calls == 1


def test_order_guard_rejects_disabled_mt5_trading_before_submission() -> None:
    fake_mt5 = FakeMt5()
    fake_mt5.account_trade_allowed = False
    adapter = Mt5TerminalAdapter(None, 10_000, module_loader=lambda _: fake_mt5)

    result = adapter.send_market_order(
        "EURUSD",
        "buy",
        0.01,
        1.0,
        1.1,
        required_trade_mode="demo",
    )

    assert result.submitted is False
    assert result.error_message == "MT5 account does not allow trading."
    assert fake_mt5.order_send_calls == 0
