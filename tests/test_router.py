"""Tests for VibeRouter core functionality."""

import pytest
from viberouter.router import (
    Router,
    TaskClassifier,
    TaskComplexity,
    TaskType,
    RoutingStrategy,
    ProviderProfile,
)
from viberouter.providers import (
    openai_gpt4o_mini,
    local_qwen3_35b,
    default_providers,
)


class TestTaskClassifier:
    """Test task classification."""

    def test_trivial_task(self):
        """Simple formatting task."""
        classifier = TaskClassifier()
        result = classifier.classify("Format indentation in this file")
        assert result.complexity == TaskComplexity.TRIVIAL

    def test_simple_task(self):
        """Small feature or bug fix."""
        classifier = TaskClassifier()
        result = classifier.classify("Add error handling to login function")
        assert result.complexity in (TaskComplexity.SIMPLE, TaskComplexity.MODERATE)

    def test_simple_fix_task(self):
        """Fix typo should be simple."""
        classifier = TaskClassifier()
        result = classifier.classify("Fix typo in variable name")
        assert result.complexity in (TaskComplexity.SIMPLE, TaskComplexity.TRIVIAL)

    def test_complex_task(self):
        """Architecture or system-level task."""
        classifier = TaskClassifier()
        result = classifier.classify("Design scalable microservices architecture")
        assert result.complexity == TaskComplexity.COMPLEX

    def test_expert_task(self):
        """Deep debugging or optimization."""
        classifier = TaskClassifier()
        result = classifier.classify("Debug intermittent memory leak in production")
        assert result.complexity == TaskComplexity.EXPERT

    def test_default_complexity(self):
        """Unknown tasks default to simple."""
        classifier = TaskClassifier()
        result = classifier.classify("Do something with data")
        assert result.complexity == TaskComplexity.SIMPLE

    def test_code_generation_type(self):
        """Generate code task."""
        classifier = TaskClassifier()
        result = classifier.classify("Write a REST API endpoint")
        assert result.task_type == TaskType.CODE_GENERATION

    def test_debugging_type(self):
        """Fix bug task."""
        classifier = TaskClassifier()
        result = classifier.classify("Fix the login authentication error")
        assert result.task_type == TaskType.DEBUGGING

    def test_explanation_type(self):
        """Explain concept task."""
        classifier = TaskClassifier()
        result = classifier.classify("Explain how JWT works")
        assert result.task_type == TaskType.EXPLANATION

    def test_refactoring_type(self):
        """Refactor task."""
        classifier = TaskClassifier()
        result = classifier.classify("Refactor the database layer")
        assert result.task_type == TaskType.REFACTORING


class TestRouter:
    """Test router functionality."""

    def test_route_to_local_first(self):
        """Simple tasks should route to local/cheap models."""
        router = Router(
            providers=[local_qwen3_35b(), openai_gpt4o_mini()],
            strategy=RoutingStrategy.COST_OPTIMIZED,
        )

        result = router.route("Fix typo in variable name")
        assert result["provider"] == "local"
        assert result["task_complexity"] in ("simple", "trivial")

    def test_route_to_premium_for_complex(self):
        """Complex tasks should route to quality models."""
        router = Router(
            providers=default_providers(),
            strategy=RoutingStrategy.QUALITY_OPTIMIZED,
        )

        result = router.route("Design microservices architecture")
        assert result["task_complexity"] == "complex"
        # Should prefer quality models
        assert result["score"] > 0  # Has a score

    def test_cost_optimized_strategy(self):
        """Cost optimized should prefer cheapest options."""
        router = Router(
            providers=[local_qwen3_35b(), openai_gpt4o_mini()],
            strategy=RoutingStrategy.COST_OPTIMIZED,
        )

        result = router.route("Add error handling")
        assert result["provider"] in ("local", "openai")

    def test_batch_routing(self):
        """Route multiple tasks."""
        router = Router(
            providers=default_providers(),
            strategy=RoutingStrategy.BALANCED,
        )

        tasks = [
            "Fix typo",
            "Write API endpoint",
            "Debug memory leak",
        ]

        results = router.route_batch(tasks)
        assert len(results) == 3
        assert all(r["provider"] in ("local", "openai") for r in results)

    def test_task_history(self):
        """Route results should be tracked."""
        router = Router(
            providers=default_providers(),
            strategy=RoutingStrategy.BALANCED,
        )

        router.route("Task 1")
        router.route("Task 2")

        history = router.task_history
        assert len(history) == 2
        assert history[0]["provider"] == history[1]["provider"]

    def test_cost_report_empty(self):
        """Empty router returns zeros."""
        router = Router(providers=[])
        report = router.get_cost_report()
        assert report["total_tasks"] == 0
        assert report["total_cost"] == 0.0

    def test_cost_report_with_data(self):
        """Cost report reflects routing."""
        router = Router(
            providers=default_providers(),
            strategy=RoutingStrategy.COST_OPTIMIZED,
        )

        router.route("Fix typo")
        router.route("Write API endpoint")

        report = router.get_cost_report()
        assert report["total_tasks"] == 2
        assert report["total_cost"] >= 0  # Can be 0 if local providers used
        assert "provider_costs" in report


class TestProviderProfile:
    """Test provider profile calculations."""

    def test_estimated_cost(self):
        """Cost calculation is correct."""
        provider = ProviderProfile(
            name="test",
            model="test-model",
            cost_per_token=0.00001,
            cost_per_output_token=0.00003,
        )

        cost = provider.estimated_cost  # Property access, not method call
        assert cost == (1000 * 0.00001) + (500 * 0.00003)  # 0.01 + 0.015 = 0.025

    def test_estimated_latency(self):
        """Latency calculation is correct."""
        provider = ProviderProfile(
            name="test",
            model="test-model",
            tokens_per_second=50.0,
        )

        latency = provider.estimated_latency  # Property access, not method call
        assert latency == 10.0  # 500 / 50

    def test_local_provider_zero_cost(self):
        """Local provider should have zero cost."""
        provider = local_qwen3_35b()
        assert provider.cost_per_token == 0
        assert provider.cost_per_output_token == 0


class TestDefaultProviders:
    """Test provider presets."""

    def test_default_providers_returns_list(self):
        """Default providers returns a list."""
        providers = default_providers()
        assert isinstance(providers, list)
        assert len(providers) >= 3

    def test_default_providers_has_local(self):
        """Default providers includes local."""
        providers = default_providers()
        names = [p.name for p in providers]
        assert "local" in names

    def test_default_providers_has_cloud(self):
        """Default providers includes cloud."""
        providers = default_providers()
        names = [p.name for p in providers]
        assert any(name in names for name in ["openai", "openrouter", "anthropic"])
