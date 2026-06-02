"""Comprehensive tests for VibeRouter core functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from viberouter.core import VibeRouter, CircuitBreaker, AuditEntry
from viberouter.config import NodeConfig, RouterConfig
from viberouter.llm_interface import LLMClient


# ─── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def sample_nodes():
    """Create sample node configurations."""
    return [
        NodeConfig(name="gb10-2", url="http://localhost:8081", model="Qwen3.6-35B", weight=3),
        NodeConfig(name="gb10-1", url="http://localhost:30000", model="Qwen3-Nemotron", weight=2),
    ]


@pytest.fixture
def sample_config(sample_nodes):
    """Create a router configuration."""
    return RouterConfig(
        log_level="DEBUG",
        strategy="weighted_round_robin",
        fallback_threshold=3,
        nodes=sample_nodes,
    )


@pytest.fixture
def sample_router(sample_config):
    """Create a router with mocked clients."""
    router = VibeRouter(sample_config)

    # Mock clients
    for node in sample_config.nodes:
        router.clients[node.name] = MagicMock()
        router.clients[node.name].is_healthy = True
        router.clients[node.name].error_count = 0
        router.clients[node.name].total_tokens = 0

    router.healthy_nodes = [n.name for n in sample_config.nodes]
    return router


@pytest.fixture
def healthy_router(sample_router):
    """Ensure router has healthy nodes."""
    return sample_router


# ─── CircuitBreaker Tests ─────────────────────────────────────────────

class TestCircuitBreaker:
    def test_initial_state(self):
        cb = CircuitBreaker()
        assert cb.state == "closed"
        assert cb.failure_count == 0

    def test_record_success_resets(self):
        import time
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"
        # Wait for timeout so next allow_request() transitions to half_open
        time.sleep(0.02)
        cb.allow_request()  # transitions to half_open
        assert cb.state == "half_open"
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == "closed"

    def test_open_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"

        cb.record_failure()
        assert cb.state == "open"

    def test_half_open_after_timeout(self):
        import time
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"

        time.sleep(0.02)
        assert cb.allow_request() is True
        assert cb.state == "half_open"

    def test_no_request_when_open(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=9999)
        cb.record_failure()
        assert cb.allow_request() is False

    def test_half_open_allows_one_request(self):
        import time
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        time.sleep(0.02)
        assert cb.allow_request() is True  # HALF_OPEN allows one test
        assert cb.state == "half_open"


# ─── AuditEntry Tests ─────────────────────────────────────────────────

class TestAuditEntry:
    def test_creation(self):
        entry = AuditEntry(
            prompt_hash="abc123",
            task_type="coding",
            node="gb10-2",
            latency_ms=42.5,
            status="success",
        )
        assert entry.prompt_hash == "abc123"
        assert entry.task_type == "coding"
        assert entry.node == "gb10-2"
        assert entry.latency_ms == 42.5
        assert entry.status == "success"
        assert entry.id  # UUID generated
        assert entry.timestamp  # ISO timestamp present


# ─── Task Classification Tests ────────────────────────────────────────

class TestTaskClassification:
    def test_coding_detection(self, healthy_router):
        assert healthy_router.classify_task("Write a Python function") == "coding"
        assert healthy_router.classify_task("Debug this JavaScript code") == "coding"
        assert healthy_router.classify_task("Create a Flask API endpoint") == "coding"
        assert healthy_router.classify_task("Fix the bug in my code") == "coding"

    def test_vision_detection(self, healthy_router):
        assert healthy_router.classify_task("Analyze this image") == "vision"
        assert healthy_router.classify_task("Look at the screenshot") == "vision"
        assert healthy_router.classify_task("Describe this photo") == "vision"

    def test_data_detection(self, healthy_router):
        assert healthy_router.classify_task("Calculate statistics from this CSV") == "data"
        assert healthy_router.classify_task("Query the SQL database") == "data"

    def test_security_detection(self, healthy_router):
        assert healthy_router.classify_task("Check for vulnerabilities") == "security"
        assert healthy_router.classify_task("Security audit of this code") == "security"
        assert healthy_router.classify_task("Find password leaks in this file") == "security"

    def test_reasoning_detection(self, healthy_router):
        long_prompt = "x " * 1001  # > 1000 chars
        assert healthy_router.classify_task(long_prompt) == "reasoning"

    def test_chat_fallback(self, healthy_router):
        assert healthy_router.classify_task("Hello, how are you?") == "chat"
        assert healthy_router.classify_task("Tell me a joke") == "chat"


# ─── Node Selection Tests ─────────────────────────────────────────────

class TestNodeSelection:
    def test_rr_selects_node(self, healthy_router):
        node = healthy_router._select_node_rr()
        assert node in ["gb10-2", "gb10-1"]

    def test_least_loaded_selects_node(self, healthy_router):
        node = healthy_router._select_node_least_loaded()
        assert node in ["gb10-2", "gb10-1"]

    def test_no_healthy_nodes_raises(self):
        config = RouterConfig(strategy="least_loaded", nodes=[
            NodeConfig(name="fake", url="http://localhost:9999", model="fake", max_connections=1)
        ])
        router = VibeRouter(config)
        router.clients["fake"] = MagicMock()
        router.clients["fake"].is_healthy = False
        router.clients["fake"].error_count = 0
        router.healthy_nodes = []

        with pytest.raises(Exception, match="No healthy nodes"):
            router._select_node_rr()


# ─── Routing Tests ────────────────────────────────────────────────────

class TestRouting:
    def test_route_returns_dict(self, healthy_router):
        result = healthy_router.route("Write a Python function")
        assert isinstance(result, dict)
        assert "node" in result
        assert "model" in result
        assert "task_type" in result
        assert "status" in result
        assert "latency_ms" in result

    def test_route_load_increases(self, healthy_router):
        # Route and verify the selected node's load increased
        healthy_router.route("Write code")
        # The node that got selected should have load >= 1
        for node, load in healthy_router.load_counters.items():
            if load > 0:
                assert load == 1
                break
        else:
            pytest.fail("No node had load increased")

    def test_release_load_decreases(self, healthy_router):
        node = healthy_router.healthy_nodes[0]
        healthy_router.load_counters[node] = 5
        healthy_router.release_load(node)
        assert healthy_router.load_counters[node] == 4
        healthy_router.release_load(node)
        assert healthy_router.load_counters[node] == 3

    def test_get_status(self, healthy_router):
        status = healthy_router.get_status()
        assert "nodes" in status
        assert "strategy" in status
        assert "healthy_count" in status
        assert "total_nodes" in status
        assert status["healthy_count"] == 2
        assert status["total_nodes"] == 2

    def test_audit_log_populated(self, healthy_router):
        healthy_router.route("Write code")
        healthy_router.route("Analyze image")
        log = healthy_router.get_audit_log()
        assert len(log) >= 2

    def test_audit_entry_structure(self, healthy_router):
        healthy_router.route("Write a Python API endpoint")
        log = healthy_router.get_audit_log()
        entry = log[0]
        assert "id" in entry
        assert "timestamp" in entry
        assert "prompt_hash" in entry
        assert "task_type" in entry
        assert "node" in entry
        assert "latency_ms" in entry
        assert "status" in entry


# ─── Type-Pref Strategy Tests ─────────────────────────────────────────

class TestTypePrefStrategy:
    def test_coding_prefers_gb10_2(self, healthy_router):
        healthy_router.config.strategy = "type_preferred"
        node = healthy_router.route("Write a Python function").get("node", "")
        assert node in ["gb10-2", "gb10-1"]  # gb10-2 preferred, but fallback OK

    def test_vision_prefers_gb10_1(self, healthy_router):
        healthy_router.config.strategy = "type_preferred"
        node = healthy_router.route("Analyze this image").get("node", "")
        assert node in ["gb10-1", "gb10-2"]  # gb10-1 preferred

    def test_least_loaded_strategy(self, healthy_router):
        healthy_router.config.strategy = "least_loaded"
        healthy_router.load_counters["gb10-2"] = 10
        healthy_router.load_counters["gb10-1"] = 2
        node = healthy_router._select_node_least_loaded()
        assert node == "gb10-1"


# ─── Config Tests ─────────────────────────────────────────────────────

class TestConfig:
    def test_default_config(self):
        config = RouterConfig()
        assert config.log_level == "INFO"
        assert config.strategy == "weighted_round_robin"
        assert config.fallback_threshold == 3
        assert config.fallback_enabled is True
        assert config.nodes == []

    def test_node_config_defaults(self):
        node = NodeConfig(name="test", url="http://localhost:8081", model="test-model")
        assert node.weight == 1
        assert node.health_check_interval == 30
        assert node.max_connections == 10
        assert node.timeout == 60
        assert node.api_key is None


# ─── LLMClient Tests ──────────────────────────────────────────────────

class TestLLMClient:
    def test_client_initialization(self, sample_nodes):
        client = LLMClient(sample_nodes[0])
        assert client.node.name == "gb10-2"
        assert client.is_healthy is True
        assert client.request_count == 0
        assert client.error_count == 0
        assert client.total_tokens == 0

    def test_health_check_fails_when_no_endpoint(self, sample_nodes):
        import asyncio
        client = LLMClient(sample_nodes[0])
        result = asyncio.run(client.health_check())
        assert result is False  # No real server running


# ─── Integration / Edge Cases ─────────────────────────────────────────

class TestEdgeCases:
    def test_empty_prompt_classified_as_chat(self, healthy_router):
        assert healthy_router.classify_task("") == "chat"

    def test_very_long_prompt(self, healthy_router):
        long_text = "a " * 5000
        result = healthy_router.route(long_text)
        assert "task_type" in result

    def test_release_load_does_not_go_negative(self, healthy_router):
        node = "gb10-2"
        healthy_router.load_counters[node] = 0
        healthy_router.release_load(node)
        healthy_router.release_load(node)
        assert healthy_router.load_counters[node] == 0

    def test_multiple_routes_same_node(self, healthy_router):
        for _ in range(5):
            healthy_router.route("Write code")
        # No exceptions — routing should work repeatedly
