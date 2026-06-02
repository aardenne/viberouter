"""Tests for VibeRouter core functionality."""

import pytest
from viberouter.core import VibeRouter
from viberouter.config import RouterConfig, NodeConfig


def test_router_initialization():
    """Test that router initializes correctly."""
    config = RouterConfig(
        nodes=[
            NodeConfig(name="test_node", url="http://localhost:8000", model="test-model"),
        ]
    )
    router = VibeRouter(config)
    assert len(router.clients) == 1
    assert "test_node" in router.clients


def test_task_classification():
    """Test task classification logic."""
    config = RouterConfig(nodes=[])
    router = VibeRouter(config)
    
    assert router.classify_task("Write a Python function") == "coding"
    assert router.classify_task("Analyze this image") == "vision"
    assert router.classify_task("Tell me about data science") == "data"
    assert router.classify_task("Check security vulnerabilities") == "security"
    assert router.classify_task("Hello world") == "chat"


def test_route_returns_result():
    """Test that routing returns a valid result."""
    config = RouterConfig(nodes=[
        NodeConfig(name="node1", url="http://localhost:8000", model="model1", weight=1),
    ])
    router = VibeRouter(config)
    
    result = router.route("Test prompt")
    assert "node" in result
    assert "model" in result
    assert "task_type" in result


def test_status_retrieval():
    """Test status retrieval."""
    config = RouterConfig(nodes=[
        NodeConfig(name="node1", url="http://localhost:8000", model="model1"),
    ])
    router = VibeRouter(config)
    
    status = router.get_status()
    assert "nodes" in status
    assert "strategy" in status
    assert "healthy_count" in status
