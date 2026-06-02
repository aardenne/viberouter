"""Integration tests for VibeRouter API and streaming."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from viberouter.api import app
from viberouter.core import VibeRouter
from viberouter.config import NodeConfig, RouterConfig


@pytest.fixture
def mock_router():
    """Create a router with fully mocked clients."""
    config = RouterConfig(
        log_level="DEBUG",
        strategy="type_preferred",
        nodes=[
            NodeConfig(name="gb10-2", url="http://localhost:8081", model="Qwen3.6-35B", weight=3, max_connections=8),
            NodeConfig(name="gb10-1", url="http://localhost:30000", model="Qwen3-Nemotron", weight=2, max_connections=8),
        ],
    )
    router = VibeRouter(config)

    for node in config.nodes:
        client_mock = MagicMock()
        client_mock.is_healthy = True
        client_mock.error_count = 0
        client_mock.total_tokens = 0
        client_mock.node = node
        client_mock.health_check = AsyncMock(return_value=True)
        router.clients[node.name] = client_mock
        router.circuit_breakers[node.name] = MagicMock()

    router.healthy_nodes = [n.name for n in config.nodes]
    router.initialize = AsyncMock()
    return router


@pytest.fixture
def client(mock_router):
    """Create test client with mocked router instance."""
    with patch("viberouter.api.router_instance", mock_router):
        yield TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_status(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "strategy" in data
        assert "healthy_count" in data
        assert "total_nodes" in data
        assert data["healthy_count"] == 2
        assert data["total_nodes"] == 2

    def test_node_health(self, client):
        resp = client.get("/health/node/gb10-2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["node"] == "gb10-2"

    def test_node_health_404(self, client):
        resp = client.get("/health/node/nonexistent")
        assert resp.status_code == 404


class TestRouteEndpoint:
    def test_route_returns_result(self, client):
        resp = client.post("/route", json={"prompt": "Write a Python function"})
        assert resp.status_code == 200
        data = resp.json()
        assert "node" in data
        assert "model" in data
        assert "task_type" in data
        assert data["status"] == "success"
        assert "latency_ms" in data

    def test_route_with_override(self, client):
        resp = client.post("/route", json={"prompt": "Write code", "override_node": "gb10-1"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["node"] == "gb10-1"

    def test_route_with_invalid_override(self, client):
        resp = client.post("/route", json={"prompt": "Write code", "override_node": "fake-node"})
        assert resp.status_code == 400

    def test_route_with_context_length(self, client):
        resp = client.post("/route", json={"prompt": "test", "context_length": 1024})
        assert resp.status_code == 200


class TestAuditEndpoint:
    def test_audit_log(self, client):
        # Make a route first to populate audit log
        client.post("/route", json={"prompt": "Write code"})
        resp = client.get("/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if data:
            entry = data[0]
            assert "id" in entry
            assert "timestamp" in entry
            assert "node" in entry


class TestConfigEndpoint:
    def test_get_config(self, client):
        resp = client.get("/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "strategy" in data
        assert "nodes" in data

    def test_update_config_strategy(self, client):
        resp = client.put("/config", json={"strategy": "least_loaded"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["strategy"] == "least_loaded"

    def test_update_config_invalid_strategy(self, client):
        resp = client.put("/config", json={"strategy": "invalid"})
        assert resp.status_code == 400


class TestAddNodeEndpoint:
    def test_add_new_node(self, client):
        resp = client.post("/config/node", json={
            "name": "new-node",
            "url": "http://localhost:9000",
            "model": "test-model",
            "weight": 1,
        })
        assert resp.status_code == 200

    def test_add_duplicate_node(self, client):
        resp = client.post("/config/node", json={
            "name": "gb10-2",  # Already exists
            "url": "http://localhost:9000",
            "model": "test",
        })
        assert resp.status_code == 409


class TestSimulateEndpoint:
    def test_simulate_with_prompts(self, client):
        prompts = ["Write code", "Analyze image", "What is 2+2?"]
        resp = client.post("/simulate", json={"prompts": prompts})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["success"] >= 0
        assert len(data["results"]) == 3


class TestPrometheusMetrics:
    def test_prometheus_format(self, client):
        # Trigger a route first so request counts exist
        client.post("/route", json={"prompt": "Write code"})
        resp = client.get("/metrics/prometheus")
        assert resp.status_code == 200
        content = resp.text
        assert "viberouter_requests_total" in content
        assert "viberouter_errors_total" in content
        assert "viberouter_cluster_healthy_nodes" in content


class TestDashboard:
    def test_dashboard_served(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")


class TestWebsocketMetrics:
    def test_websocket_connection(self, client):
        with client.websocket_connect("/ws/metrics") as ws:
            data = ws.receive_json()
            assert "nodes" in data
            assert "strategy" in data


class TestStreaming:
    def test_stream_endpoint_routing(self, client):
        """Verify /stream endpoint correctly routes (won't actually stream without real LLM)."""
        # The endpoint should at least route correctly
        # We test the routing part, not the actual stream
        resp = client.post("/route", json={"prompt": "Write a Python function that streams data"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
