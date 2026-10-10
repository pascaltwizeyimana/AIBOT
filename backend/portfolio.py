"""In-memory paper-trading account for safe local workflow testing."""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from threading import Lock


@dataclass
class PaperOrder:
    id: int
    symbol: str
    side: str
    quantity: float
    entry_price: float
    status: str
    opened_at: str
    exit_price: float | None = None
    realized_pnl: float = 0.0


class PaperPortfolio:
    def __init__(self) -> None:
        self._lock = Lock()
        self.reset()

    def reset(self) -> None:
        with getattr(self, "_lock", Lock()):
            self.starting_balance = 10_000.0
            self.cash = 10_000.0
            self.orders: list[PaperOrder] = []
            self.next_id = 1
            self.tick = 0

    def _price(self, symbol: str) -> float:
        base = 1.0 + (sum(ord(character) for character in symbol) % 100) / 100
        return round(base + self.tick * 0.0005, 5)

    def open_order(self, symbol: str, side: str, quantity: float) -> PaperOrder:
        with self._lock:
            self.tick += 1
            order = PaperOrder(
                id=self.next_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                entry_price=self._price(symbol),
                status="open",
                opened_at=datetime.now(UTC).isoformat(),
            )
            self.next_id += 1
            self.orders.append(order)
            return order

    def close_all(self) -> None:
        with self._lock:
            self.tick += 1
            for order in self.orders:
                if order.status == "open":
                    order.exit_price = self._price(order.symbol)
                    multiplier = 1 if order.side == "buy" else -1
                    order.realized_pnl = round(
                        (order.exit_price - order.entry_price) * order.quantity * multiplier,
                        2,
                    )
                    order.status = "closed"
            self.cash = self.starting_balance + self._realized_pnl()

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            open_orders = [order for order in self.orders if order.status == "open"]
            unrealized = 0.0
            for order in open_orders:
                current = self._price(order.symbol)
                multiplier = 1 if order.side == "buy" else -1
                unrealized += (current - order.entry_price) * order.quantity * multiplier
            realized = self._realized_pnl()
            return {
                "mode": "paper",
                "starting_balance": self.starting_balance,
                "cash": round(self.cash, 2),
                "equity": round(self.cash + unrealized, 2),
                "realized_pnl": round(realized, 2),
                "unrealized_pnl": round(unrealized, 2),
                "total_pnl": round(realized + unrealized, 2),
                "open_orders": [asdict(order) for order in open_orders],
                "closed_orders": [
                    asdict(order) for order in self.orders if order.status == "closed"
                ],
            }

    def _realized_pnl(self) -> float:
        return sum(order.realized_pnl for order in self.orders if order.status == "closed")


paper_portfolio = PaperPortfolio()
