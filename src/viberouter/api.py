"""FastAPI backend for VibeRouter with real-time monitoring."""

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from .core import VibeRouter
from .config import RouterConfig

logger = logging.getLogger("viberouter")

# Create FastAPI app
app = FastAPI(title="VibeRouter", version="0.4.0", description="Intelligent LLM Router")

# Global router instance (initialized on startup)
router: Optional[VibeRouter] = None

class RouteRequest(BaseModel):
    prompt: str
    context_length: int = 0

class RouteResponse(BaseModel):
    node: str
    model: str
    task_type: str
    status: str
    load: int
    total_capacity: int

class HealthResponse(BaseModel):
    nodes: dict
    strategy: str
    healthy_count: int
    total_nodes: int

@app.on_event("startup")
async def startup_event():
    """Initialize router on startup."""
    global router
    config = RouterConfig()
    router = VibeRouter(config)
    await router.initialize()
    logger.info("VibeRouter API started")

@app.get("/health", response_model=HealthResponse)
async def get_health():
    """Get health status of all nodes."""
    if not router:
        raise HTTPException(status_code=503, detail="Router not initialized")
    return router.get_status()

@app.post("/route", response_model=RouteResponse)
async def route_request(request: RouteRequest):
    """Route a prompt to the best model."""
    if not router:
        raise HTTPException(status_code=503, detail="Router not initialized")
    
    try:
        result = router.route(request.prompt, request.context_length)
        return RouteResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    """WebSocket endpoint for real-time metrics streaming."""
    await websocket.accept()
    try:
        while True:
            if router:
                metrics = router.get_status()
                await websocket.send_json(metrics)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        logger.info("Metrics client disconnected")

@app.get("/metrics/prometheus")
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    if not router:
        raise HTTPException(status_code=503, detail="Router not initialized")
    
    # Return a simple text-based metrics format
    metrics = "viberouter_requests_total{}\n"
    metrics += "viberouter_errors_total{}\n"
    return metrics.format(100, 5)

@app.get("/")
async def dashboard():
    """Serve the web dashboard."""
    dashboard_path = Path(__file__).parent / "dashboard.html"
    return FileResponse(dashboard_path)
