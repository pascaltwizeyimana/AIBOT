"""Versioned API router assembly."""

from fastapi import APIRouter

from backend.api.routes.analysis import router as analysis_router
from backend.api.routes.demo_execution import router as demo_execution_router
from backend.api.routes.health import router as health_router
from backend.api.routes.live import router as live_router
from backend.api.routes.live_execution import router as live_execution_router
from backend.api.routes.market import router as market_router
from backend.api.routes.paper import router as paper_router
from backend.api.routes.system import router as system_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router, tags=["system"])
api_router.include_router(live_router, tags=["live-market"])
api_router.include_router(live_execution_router, tags=["live-execution"])
api_router.include_router(system_router, tags=["system"])
api_router.include_router(market_router, tags=["market-data"])
api_router.include_router(analysis_router, tags=["analysis"])
api_router.include_router(paper_router, tags=["paper-trading"])
api_router.include_router(demo_execution_router, tags=["demo-execution"])
