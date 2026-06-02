"""Core LLM Router logic for VibeRouter with advanced load balancing, auto-fallback, and monitoring."""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Literal, Optional, List, Tuple
from collections import defaultdict, deque
from .config import NodeConfig, RouterConfig
from .llm_interface import LLMClient

logger = logging.getLogger("viberouter")

ModelType = Literal["coding", "reasoning", "vision", "chat", "simple", "data", "security"]


class AuditEntry:
    """Audit log entry for all routing decisions."""
    __slots__ = ('id', 'timestamp', 'prompt_hash', 'task_type', 'node', 'latency_ms', 'status')

    def __init__(self, prompt_hash: str, task_type: str, node: str, latency_ms: float, status: str):
        self.id = uuid.uuid4().hex[:8]
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.prompt_hash = prompt_hash
        self.task_type = task_type
        self.node = node
        self.latency_ms = latency_ms
        self.status = status


class CircuitBreaker:
    """Circuit breaker for individual nodes."""

    CLOSED = "closed"    # Normal operation
    OPEN = "open"        # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = self.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None

    def record_success(self):
        """Record a successful request."""
        self.failure_count = 0
        if self.state == self.HALF_OPEN:
            self.state = self.CLOSED
            logger.info(f"Circuit breaker CLOSED for node")

    def record_failure(self):
        """Record a failed request."""
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.failure_threshold:
            self.state = self.OPEN
            logger.warning(f"Circuit breaker OPEN for node after {self.failure_count} failures")

    def allow_request(self) -> bool:
        """Check if request is allowed."""
        if self.state == self.CLOSED:
            return True
        if self.state == self.OPEN:
            if self.last_failure_time and (time.monotonic() - self.last_failure_time) > self.recovery_timeout:
                self.state = self.HALF_OPEN
                logger.info(f"Circuit breaker HALF_OPEN for node (timeout elapsed)")
                return True
            return False
        # HALF_OPEN: allow one test request
        return self.state == self.HALF_OPEN


class VibeRouter:
    """Advanced router with load balancing, circuit breaker, and audit logging."""

    def __init__(self, config: RouterConfig):
        self.config = config
        self.clients: Dict[str, LLMClient] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.node_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "requests": 0, "errors": 0, "tokens": 0, "latencies": [],
            "health_checks": 0, "first_seen": datetime.now(timezone.utc).isoformat()
        })
        self.load_counters: Dict[str, int] = {node.name: 0 for node in config.nodes}
        self.audit_log: deque = deque(maxlen=500)
        self._request_counter = 0

        # Initialize clients and circuit breakers
        for node in config.nodes:
            self.clients[node.name] = LLMClient(node)
            self.circuit_breakers[node.name] = CircuitBreaker(
                failure_threshold=config.fallback_threshold,
                recovery_timeout=30.0
            )

        logger.info(f"Initialized VibeRouter with {len(self.clients)} nodes")

    async def initialize(self):
        """Run initial health checks on all nodes."""
        tasks = [self.health_check(name) for name in self.clients]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for name, result in zip(self.clients, results):
            if isinstance(result, Exception):
                logger.error(f"Health check exception for {name}: {result}")
        self._update_status()

    async def health_check(self, node_name: str) -> bool:
        """Run health check on a specific node."""
        client = self.clients[node_name]
        try:
            result = await client.health_check()
            self.node_stats[node_name]["health_checks"] += 1
            if result:
                logger.info(f"Node {node_name} is healthy")
            else:
                logger.warning(f"Node {node_name} failed health check")
            return result
        except Exception as e:
            logger.error(f"Health check failed for {node_name}: {e}")
            self.node_stats[node_name]["errors"] += 1
            return False

    def _update_status(self):
        """Update global status from node stats."""
        healthy_nodes = [
            name for name, client in self.clients.items()
            if client.is_healthy and client.error_count < self.config.fallback_threshold
        ]
        self.healthy_nodes = healthy_nodes
        logger.info(f"Healthy nodes: {healthy_nodes}")

    def classify_task(self, prompt: str) -> ModelType:
        """Classify task type using heuristics and context analysis."""
        prompt_lower = prompt.lower().strip()

        # Security detection (before coding, as "code" in prompts can be ambiguous)
        if any(word in prompt_lower for word in [
            "security", "vulnerability", "vulnerabilities", "exploit", "malware", "hack",
            "password", "encryption", "auth", "authentication", "safe"
        ]):
            return "security"

        # Coding detection
        if any(word in prompt_lower for word in [
            "code", "python", "javascript", "typescript", "function", "class",
            "api", "endpoint", "route", "endpoint", "debug", "fix", "bug",
            "implement", "write a", "create a", "build", "script"
        ]):
            return "coding"

        # Vision detection
        if any(word in prompt_lower for word in [
            "image", "photo", "picture", "vision", "analyze", "look at",
            "screenshot", "diagram", "chart", "graph", "ocr", "recognize"
        ]):
            return "vision"

        # Data detection
        if any(word in prompt_lower for word in [
            "data", "analytics", "statistics", "csv", "json", "sql",
            "database", "query", "report", "calculate", "compute", "sum"
        ]):
            return "data"

        # Reasoning detection (long prompts)
        if len(prompt) > 1000:
            return "reasoning"

        # Chat default
        return "chat"

    def _select_node_rr(self) -> str:
        """Weighted Round Robin selection."""
        nodes = self.healthy_nodes
        if not nodes:
            raise Exception("No healthy nodes available")

        min_load = min(self.load_counters[n] for n in nodes)
        candidates = [n for n in nodes if self.load_counters[n] == min_load]

        weighted_candidates = []
        for node in candidates:
            config_node = next((n for n in self.config.nodes if n.name == node), None)
            if config_node:
                weighted_candidates.extend([node] * config_node.weight)

        import random
        return random.choice(weighted_candidates) if weighted_candidates else candidates[0]

    def _select_node_least_loaded(self) -> str:
        """Select least loaded node."""
        if not self.healthy_nodes:
            raise Exception("No healthy nodes available")
        return min(self.healthy_nodes, key=lambda n: self.load_counters[n])

    def _get_preferred_node(self, task_type: ModelType) -> Optional[str]:
        """Get the preferred node for a task type (if configured)."""
        # Node-type mapping for smart routing
        type_preferences: Dict[str, List[str]] = {
            "coding": ["gb10-2", "gb10-1"],  # Qwen3.6 first
            "vision": ["gb10-1", "gb10-2"],  # Nemotron first
            "reasoning": ["gb10-2"],
            "chat": ["gb10-2", "gb10-1"],
            "data": ["gb10-2"],
            "security": ["gb10-2"],
            "simple": ["gb10-1"],  # Fast response preferred
        }

        preferences = type_preferences.get(task_type, [])
        for pref in preferences:
            if pref in self.healthy_nodes:
                return pref
        return None

    def route(self, prompt: str, context_length: int = 0) -> Dict[str, Any]:
        """Route a task to the best available node."""
        start_time = time.monotonic()
        self._request_counter += 1

        try:
            task_type = self.classify_task(prompt)
            prompt_hash = uuid.uuid5(uuid.NAMESPACE_DNS, prompt[:50]).hex[:8]

            # Strategy-based selection
            if self.config.strategy == "least_loaded":
                node_name = self._select_node_least_loaded()
            elif self.config.strategy == "type_preferred":
                preferred = self._get_preferred_node(task_type)
                if preferred:
                    node_name = preferred
                else:
                    node_name = self._select_node_rr()
            else:  # Default: weighted round robin
                node_name = self._select_node_rr()

            # Increment counters
            self.load_counters[node_name] += 1
            self.node_stats[node_name]["requests"] += 1

            # Get node config
            node_config = next(n for n in self.config.nodes if n.name == node_name)

            latency_ms = (time.monotonic() - start_time) * 1000

            # Audit log
            self.audit_log.append(AuditEntry(
                prompt_hash=prompt_hash,
                task_type=task_type,
                node=node_name,
                latency_ms=latency_ms,
                status="success"
            ))

            logger.info(f"Routed #{self._request_counter}: {task_type} -> {node_name} ({latency_ms:.0f}ms)")

            return {
                "request_id": self._request_counter,
                "node": node_name,
                "model": node_config.model,
                "task_type": task_type,
                "status": "success",
                "load": self.load_counters[node_name],
                "total_capacity": node_config.max_connections,
                "latency_ms": round(latency_ms, 2),
            }

        except Exception as e:
            latency_ms = (time.monotonic() - start_time) * 1000
            self.audit_log.append(AuditEntry(
                prompt_hash="",
                task_type="",
                node="unknown",
                latency_ms=latency_ms,
                status="failed"
            ))
            logger.error(f"Routing error: {e}")
            return {"error": str(e), "status": "failed", "latency_ms": round(latency_ms, 2)}

    def release_load(self, node_name: str):
        """Release load from a node after request completion."""
        if node_name in self.load_counters:
            self.load_counters[node_name] = max(0, self.load_counters[node_name] - 1)

    def record_request_result(self, node_name: str, success: bool):
        """Record whether a routed request succeeded (for circuit breaker)."""
        if success:
            self.circuit_breakers[node_name].record_success()
        else:
            self.circuit_breakers[node_name].record_failure()
            self.node_stats[node_name]["errors"] += 1

    def get_audit_log(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent audit log entries."""
        return [
            {
                "id": entry.id,
                "timestamp": entry.timestamp,
                "prompt_hash": entry.prompt_hash,
                "task_type": entry.task_type,
                "node": entry.node,
                "latency_ms": round(entry.latency_ms, 2),
                "status": entry.status,
            }
            for entry in list(self.audit_log)[:limit]
        ]

    def get_status(self) -> Dict[str, Any]:
        """Get current router status."""
        return {
            "nodes": {
                name: {
                    "model": client.node.model,
                    "healthy": client.is_healthy,
                    "load": self.load_counters.get(name, 0),
                    "requests": self.node_stats[name]["requests"],
                    "errors": self.node_stats[name]["errors"],
                    "tokens": client.total_tokens,
                }
                for name, client in self.clients.items()
            },
            "strategy": self.config.strategy,
            "healthy_count": len(self.healthy_nodes),
            "total_nodes": len(self.clients),
        }
