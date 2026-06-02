"""FastAPI backend for VibeRouter with real-time monitoring."""

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from .core import VibeRouter
from .config import RouterConfig, NodeConfig
from .llm_interface import LLMClient

logger = logging.getLogger("viberouter")

# Create FastAPI app
app = FastAPI(title="VibeRouter", version="0.5.0", description="Intelligent LLM Router — Enterprise Multi-Node Load Balancer")

# Global router instance
router_instance: Optional[VibeRouter] = None


# ─── Request/Response Models ──────────────────────────────────────────

class RouteRequest(BaseModel):
    prompt: str
    context_length: int = Field(default=0, ge=0, le=131072)
    override_node: Optional[str] = None


class RouteResponse(BaseModel):
    request_id: int
    node: str
    model: str
    task_type: str
    status: str
    load: int
    total_capacity: int
    latency_ms: float


class HealthResponse(BaseModel):
    nodes: dict
    strategy: str
    healthy_count: int
    total_nodes: int


class AuditEntryResponse(BaseModel):
    id: str
    timestamp: str
    prompt_hash: str
    task_type: str
    node: str
    latency_ms: float
    status: str


class ConfigUpdate(BaseModel):
    strategy: Optional[str] = None
    log_level: Optional[str] = None


class NodeAdd(BaseModel):
    name: str
    url: str
    model: str
    weight: int = 1
    max_connections: int = 10
    timeout: int = 60
    api_key: Optional[str] = None


class SimulateRequest(BaseModel):
    prompts: List[str]


class SimulateResult(BaseModel):
    node: str
    model: str
    task_type: str
    success: bool


# ─── Startup / Shutdown ───────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Initialize router on startup."""
    global router_instance
    config = RouterConfig()
    router_instance = VibeRouter(config)
    await router_instance.initialize()
    logger.info("VibeRouter API started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global router_instance
    if router_instance:
        for client in router_instance.clients.values():
            await client.close()
        logger.info("VibeRouter API shut down")


# ─── Health & Status ──────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def get_health():
    """Get health status of all nodes."""
    if not router_instance:
        raise HTTPException(status_code=503, detail="Router not initialized")
    return router_instance.get_status()


@app.get("/health/node/{node_name}")
async def node_health(node_name: str):
    """Health check for a specific node."""
    if not router_instance:
        raise HTTPException(status_code=503, detail="Router not initialized")
    if node_name not in router_instance.clients:
        raise HTTPException(status_code=404, detail=f"Node '{node_name}' not found")

    try:
        healthy = await router_instance.clients[node_name].health_check()
        router_instance.node_stats[node_name]["health_checks"] += 1
        return {"node": node_name, "healthy": healthy}
    except Exception as e:
        return {"node": node_name, "healthy": False, "error": str(e)}


# ─── Routing ──────────────────────────────────────────────────────────

@app.post("/route", response_model=RouteResponse)
async def route_request(request: RouteRequest):
    """Route a prompt to the best model."""
    if not router_instance:
        raise HTTPException(status_code=503, detail="Router not initialized")

    try:
        if request.override_node:
            if request.override_node not in router_instance.clients:
                raise HTTPException(status_code=400, detail=f"Unknown node: {request.override_node}")
            node_name = request.override_node
            task_type = router_instance.classify_task(request.prompt)
            router_instance.load_counters[node_name] += 1
            node_config = next(n for n in router_instance.config.nodes if n.name == node_name)

            return RouteResponse(
                request_id=router_instance._request_counter + 1,
                node=node_name,
                model=node_config.model,
                task_type=task_type,
                status="success",
                load=router_instance.load_counters[node_name],
                total_capacity=node_config.max_connections,
                latency_ms=0.0,
            )

        result = router_instance.route(request.prompt, request.context_length)
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return RouteResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Route error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Audit Log ────────────────────────────────────────────────────────

@app.get("/audit", response_model=List[AuditEntryResponse])
async def get_audit_log(limit: int = Query(default=20, ge=1, le=100)):
    """Get recent audit log entries."""
    if not router_instance:
        raise HTTPException(status_code=503, detail="Router not initialized")
    return router_instance.get_audit_log(limit)


# ─── Configuration ────────────────────────────────────────────────────

@app.get("/config")
async def get_config():
    """Get current router configuration."""
    if not router_instance:
        raise HTTPException(status_code=503, detail="Router not initialized")

    config = router_instance.config
    return {
        "strategy": config.strategy,
        "log_level": config.log_level,
        "fallback_enabled": config.fallback_enabled,
        "fallback_threshold": config.fallback_threshold,
        "nodes": [
            {
                "name": n.name,
                "url": n.url,
                "model": n.model,
                "weight": n.weight,
                "health_check_interval": n.health_check_interval,
                "max_connections": n.max_connections,
            }
            for n in config.nodes
        ],
    }


@app.put("/config")
async def update_config(update: ConfigUpdate):
    """Update router configuration."""
    if not router_instance:
        raise HTTPException(status_code=503, detail="Router not initialized")

    config = router_instance.config
    if update.strategy:
        valid = {"weighted_round_robin", "least_connections", "least_loaded", "type_preferred"}
        if update.strategy not in valid:
            raise HTTPException(status_code=400, detail=f"Invalid strategy. Use one of: {valid}")
        config.strategy = update.strategy

    if update.log_level:
        config.log_level = update.log_level.upper()

    logger.info(f"Config updated: strategy={config.strategy}, log_level={config.log_level}")
    return await get_config()


@app.post("/config/node")
async def add_node(node: NodeAdd):
    """Add a new node at runtime."""
    if not router_instance:
        raise HTTPException(status_code=503, detail="Router not initialized")

    if node.name in router_instance.clients:
        raise HTTPException(status_code=409, detail=f"Node '{node.name}' already exists")

    new_node = NodeConfig(
        name=node.name, url=node.url, model=node.model,
        weight=node.weight, max_connections=node.max_connections,
        timeout=node.timeout, api_key=node.api_key,
    )
    router_instance.config.nodes.append(new_node)
    router_instance.clients[node.name] = LLMClient(new_node)
    from .core import CircuitBreaker
    router_instance.circuit_breakers[node.name] = CircuitBreaker(
        failure_threshold=router_instance.config.fallback_threshold,
        recovery_timeout=30.0,
    )
    router_instance.load_counters[node.name] = 0
    router_instance.node_stats[node.name]

    await router_instance.health_check(node.name)
    router_instance._update_status()

    logger.info(f"Node added: {node.name}")
    return {"status": "ok", "node": node.name}


# ─── Simulation ───────────────────────────────────────────────────────

@app.post("/simulate")
async def simulate(request: SimulateRequest):
    """Run a simulation with multiple prompts."""
    if not router_instance:
        raise HTTPException(status_code=503, detail="Router not initialized")

    results = []
    for prompt in request.prompts:
        try:
            result = router_instance.route(prompt)
            results.append(SimulateResult(
                node=result.get("node", "unknown"),
                model=result.get("model", "unknown"),
                task_type=result.get("task_type", "unknown"),
                success=result.get("status") == "success",
            ))
        except Exception:
            results.append(SimulateResult(
                node="error", model="error", task_type="error", success=False
            ))

    total = len(results)
    success = sum(1 for r in results if r.success)

    return {
        "total": total,
        "success": success,
        "failed": total - success,
        "results": results,
    }


# ─── Metrics ──────────────────────────────────────────────────────────

@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    """WebSocket endpoint for real-time metrics streaming."""
    await websocket.accept()
    try:
        while True:
            if router_instance:
                metrics = router_instance.get_status()
                await websocket.send_json(metrics)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        logger.info("Metrics client disconnected")


@app.get("/metrics/prometheus")
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    if not router_instance:
        raise HTTPException(status_code=503, detail="Router not initialized")

    lines = []
    total_requests = 0
    total_errors = 0

    for name, stats in router_instance.node_stats.items():
        req = stats["requests"]
        err = stats["errors"]
        total_requests += req
        total_errors += err
        lines.append(f'# HELP viberouter_requests_total Total routed requests per node')
        lines.append(f'# TYPE viberouter_requests_total counter')
        lines.append(f'viberouter_requests_total{{node="{name}"}} {req}')
        lines.append(f'viberouter_errors_total{{node="{name}"}} {err}')
        lines.append(f'viberouter_tokens_total{{node="{name}"}} {router_instance.clients[name].total_tokens}')

    lines.append(f'# HELP viberouter_cluster_healthy_nodes Current healthy nodes')
    lines.append(f'# TYPE viberouter_cluster_healthy_nodes gauge')
    lines.append(f'viberouter_cluster_healthy_nodes {len(router_instance.healthy_nodes)}')
    lines.append(f'viberouter_cluster_total_nodes {len(router_instance.clients)}')
    lines.append(f'# HELP viberouter_routing_strategy Current strategy')
    lines.append(f'# TYPE viberouter_routing_strategy gauge')
    lines.append(f'viberouter_routing_strategy{{name="{router_instance.config.strategy}"}} 1')

    return Response(content="\n".join(lines) + "\n", media_type="text/plain")


# ─── Streaming ────────────────────────────────────────────────────────

class StreamRequest(BaseModel):
    prompt: str
    context_length: int = 0
    stream: bool = True


@app.post("/stream")
async def stream_route(request: StreamRequest):
    """Route a prompt and stream response from the target node."""
    from fastapi.responses import StreamingResponse

    if not router_instance:
        raise HTTPException(status_code=503, detail="Router not initialized")

    try:
        result = router_instance.route(request.prompt, request.context_length)
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        node_name = result["node"]
        client = router_instance.clients[node_name]

        async def generate():
            try:
                # Build messages from prompt
                messages = [{"role": "user", "content": request.prompt}]
                async for chunk in client.chat_stream(messages, temperature=0.7):
                    yield f"data: {chunk}\n\n"
            finally:
                router_instance.release_load(node_name)

        return StreamingResponse(generate(), media_type="text/event-stream")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stream error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Dashboard ─────────────────────────────────────────────────────────

@app.get("/")
async def dashboard():
    """Serve the web dashboard."""
    dashboard_path = Path(__file__).parent / "dashboard.html"
    return FileResponse(dashboard_path)
