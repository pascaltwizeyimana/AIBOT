"""Safe paper-trading endpoints; these never connect to or submit to MT5."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.portfolio import paper_portfolio

router = APIRouter(prefix="/paper")


class PaperOrderRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    side: str
    quantity: float = Field(gt=0, le=1_000_000)


class AutoBatchRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    quantity: float = Field(default=1, gt=0, le=1_000_000)
    orders: int = Field(default=5, ge=1, le=100)


def validate_side(side: str) -> str:
    normalized = side.lower()
    if normalized not in {"buy", "sell"}:
        raise HTTPException(status_code=422, detail="Side must be buy or sell.")
    return normalized


@router.get("/account")
def account() -> dict[str, object]:
    return paper_portfolio.snapshot()


@router.post("/orders")
def create_order(request: PaperOrderRequest) -> dict[str, object]:
    order = paper_portfolio.open_order(
        request.symbol.strip(), validate_side(request.side), request.quantity
    )
    return {"order": order.__dict__, "account": paper_portfolio.snapshot()}


@router.post("/auto")
def create_auto_batch(request: AutoBatchRequest) -> dict[str, object]:
    for index in range(request.orders):
        paper_portfolio.open_order(
            request.symbol.strip(), "buy" if index % 2 == 0 else "sell", request.quantity
        )
    return paper_portfolio.snapshot()


@router.post("/close-all")
def close_all() -> dict[str, object]:
    paper_portfolio.close_all()
    return paper_portfolio.snapshot()


@router.post("/reset")
def reset() -> dict[str, object]:
    paper_portfolio.reset()
    return paper_portfolio.snapshot()
