"""Core LLM Router logic for VibeRouter with advanced load balancing and auto-fallback."""

import asyncio
import logging
from typing import Dict, Any, Literal, Optional
from collections import defaultdict
from .config import NodeConfig, RouterConfig
from .llm_interface import LLMClient

logger = logging.getLogger("viberouter")

ModelType = Literal["coding", "reasoning", "vision", "chat", "simple", "data", "security"]

class VibeRouter:
    """Advanced router with load balancing, auto-fallback, and monitoring."""

    def __init__(self, config: RouterConfig):
        self.config = config
        self.clients: Dict[str, LLMClient] = {}
        self.node_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {
            "requests": 0, "errors": 0, "tokens": 0, "latencies": [], "health_checks": 0
        })
        self.load_counters: Dict[str, int] = {node.name: 0 for node in config.nodes}
        
        # Initialize clients
        for node in config.nodes:
            self.clients[node.name] = LLMClient(node)

        logger.info(f"Initialized VibeRouter with {len(self.clients)} nodes")

    async def initialize(self):
        """Run initial health checks on all nodes."""
        tasks = [self.health_check(name) for name in self.clients]
        await asyncio.gather(*tasks, return_exceptions=True)
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
        prompt_lower = prompt.lower()
        
        if any(word in prompt_lower for word in ["code", "python", "function", "class", "api", "endpoint"]):
            return "coding"
        elif any(word in prompt_lower for word in ["image", "photo", "vision", "analyze", "look at"]):
            return "vision"
        elif any(word in prompt_lower for word in ["data", "analytics", "statistics", "csv", "json"]):
            return "data"
        elif any(word in prompt_lower for word in ["security", "vulnerability", "exploit", "malware"]):
            return "security"
        elif len(prompt) > 1000:
            return "reasoning"
        return "chat"

    def _select_node_rr(self) -> str:
        """Weighted Round Robin selection."""
        nodes = self.healthy_nodes
        if not nodes:
            raise Exception("No healthy nodes available")
        
        # Find node with lowest current load
        min_load = min(self.load_counters[n] for n in nodes)
        candidates = [n for n in nodes if self.load_counters[n] == min_load]
        
        # Use weight to prioritize
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

    def route(self, prompt: str, context_length: int = 0) -> Dict[str, Any]:
        """Route a task to the best available node."""
        try:
            task_type = self.classify_task(prompt)
            
            # Strategy-based selection
            if self.config.strategy == "least_loaded":
                node_name = self._select_node_least_loaded()
            else:  # Default to weighted round robin
                node_name = self._select_node_rr()
            
            # Increment load counter
            self.load_counters[node_name] += 1
            self.node_stats[node_name]["requests"] += 1
            
            # Get node config
            node_config = next(n for n in self.config.nodes if n.name == node_name)
            
            return {
                "node": node_name,
                "model": node_config.model,
                "task_type": task_type,
                "status": "success",
                "load": self.load_counters[node_name],
                "total_capacity": node_config.max_connections,
            }
        except Exception as e:
            logger.error(f"Routing error: {e}")
            return {"error": str(e), "status": "failed"}

    def release_load(self, node_name: str):
        """Release load from a node after request completion."""
        if node_name in self.load_counters:
            self.load_counters[node_name] = max(0, self.load_counters[node_name] - 1)

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
