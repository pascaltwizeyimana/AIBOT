from fastapi.testclient import TestClient

from backend.api.routes.paper import paper_portfolio
from backend.main import app


def test_paper_orders_support_manual_auto_and_pnl() -> None:
    paper_portfolio.reset()
    with TestClient(app) as client:
        manual = client.post(
            "/api/v1/paper/orders",
            json={"symbol": "EURUSDm", "side": "buy", "quantity": 10},
        )
        assert manual.status_code == 200

        batch = client.post(
            "/api/v1/paper/auto",
            json={"symbol": "EURUSDm", "quantity": 5, "orders": 4},
        )
        assert batch.status_code == 200
        assert len(batch.json()["open_orders"]) == 5

        closed = client.post("/api/v1/paper/close-all")
        assert closed.status_code == 200
        assert closed.json()["open_orders"] == []
        assert len(closed.json()["closed_orders"]) == 5
        assert closed.json()["total_pnl"] != 0


def test_paper_orders_reject_invalid_side() -> None:
    paper_portfolio.reset()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/paper/orders",
            json={"symbol": "EURUSDm", "side": "hold", "quantity": 1},
        )
    assert response.status_code == 422
