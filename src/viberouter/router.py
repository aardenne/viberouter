"""Core router engine — Task classification and model selection."""

from __future__ import annotations

import re
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import tiktoken

logger = logging.getLogger(__name__)


class TaskComplexity(Enum):
    """Task complexity levels."""
    TRIVIAL = "trivial"      # Formatting, comments, simple fixes
    SIMPLE = "simple"        # Small features, bug fixes, explanations
    MODERATE = "moderate"    # Multi-file changes, refactoring
    COMPLEX = "complex"      # Architecture changes, new systems
    EXPERT = "expert"        # Performance optimization, debugging hard issues


class TaskType(Enum):
    """Primary task type."""
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    DEBUGGING = "debugging"
    EXPLANATION = "explanation"
    PLANNING = "planning"
    DOCUMENTATION = "documentation"
    REFACTORING = "refactoring"
    OPTIMIZATION = "optimization"
    TESTING = "testing"


class RoutingStrategy(Enum):
    """Routing strategies."""
    COST_OPTIMIZED = "cost_optimized"      # Minimize cost, maintain quality
    SPEED_OPTIMIZED = "speed_optimized"    # Minimize latency
    QUALITY_OPTIMIZED = "quality_optimized"  # Best quality regardless of cost
    BALANCED = "balanced"                  # Smart mix


@dataclass
class TaskProfile:
    """Profile of a coding task for routing decisions."""
    text: str
    complexity: TaskComplexity = TaskComplexity.SIMPLE
    task_type: TaskType = TaskType.CODE_GENERATION
    context_tokens: int = 0
    requires_context_window: int = 0

    @property
    def token_count(self) -> int:
        """Approximate token count of task description."""
        if self.context_tokens > 0:
            return self.context_tokens
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(self.text))
        except Exception:
            return len(self.text) // 4  # Rough estimate


@dataclass
class ProviderProfile:
    """Performance and cost profile for an AI provider."""
    name: str
    model: str
    cost_per_token: float = 0.00001  # $/token input
    cost_per_output_token: float = 0.00003  # $/token output
    tokens_per_second: float = 50.0  # Average generation speed
    max_context_window: int = 128000
    max_recommended_context: int = 64000
    quality_score: float = 0.7  # 0-1, relative quality
    reliability_score: float = 0.95  # Success rate
    latency_p99: float = 5.0  # Seconds

    @property
    def estimated_cost(self) -> float:
        """Estimate cost for typical task (1000 input, 500 output)."""
        return (1000 * self.cost_per_token) + (500 * self.cost_per_output_token)

    @property
    def estimated_latency(self) -> float:
        """Estimate latency for typical response (500 output tokens)."""
        return 500 / self.tokens_per_second


class TaskClassifier:
    """Classifies coding tasks by complexity and type."""

    # Complexity keywords
    COMPLEXITY_PATTERNS = {
        TaskComplexity.TRIVIAL: [
            r"\b(format|reformat|whitespace|indent|comment|typo|style)\b",
            r"\b(simple|trivial|minor|small)\b",
        ],
        TaskComplexity.SIMPLE: [
            r"\b(fix|add|create|write|implement|debug|explain)\b",
            r"\b(single|one|this|that|it)\b",
            r"\b(bug|issue|error|problem)\b",
        ],
        TaskComplexity.MODERATE: [
            r"\b(refactor|restructure|redesign|migrate|upgrade|rework)\b",
            r"\b(multiple|several|various|all\s+files)\b",
            r"\b(pattern|architecture|framework|module|component)\b",
        ],
        TaskComplexity.COMPLEX: [
            r"\b(system|platform|infrastructure|architecture|scal|performance)\b",
            r"\b(optimize|accelerate|improve\s+speed|reduce\s+latency)\b",
            r"\b(production|enterprise|critical|security|auth|payment)\b",
        ],
        TaskComplexity.EXPERT: [
            r"\b(hard|difficult|complex|tricky|persistent|intermittent)\b",
            r"\b(debug.*deeply|root\s+cause|investigate.*carefully)\b",
            r"\b(benchmark|profile|analyze.*memory|analyze.*cpu)\b",
        ],
    }

    # Task type keywords
    TASK_TYPE_PATTERNS = {
        TaskType.CODE_GENERATION: [
            r"\b(writ|creat|build|develop|implement|make|generate|code)\b",
        ],
        TaskType.CODE_REVIEW: [
            r"\b(rev|review|critique|assess|evaluate|check|audit)\b",
            r"\b(code\s+rev|pull\s+request|pr\s+rev)\b",
        ],
        TaskType.DEBUGGING: [
            r"\b(debug|fix.*bug|fix.*error|fix.*crash|fix.*fail|resolve.*issue)\b",
            r"\b(stack\s+trace|traceback|exception|error\s+msg)\b",
        ],
        TaskType.EXPLANATION: [
            r"\b(explain|how\s+does|what\s+is|why\s+does|what\s+does|clarify)\b",
            r"\b(does?\s+work|workings|concept|theory|principle)\b",
        ],
        TaskType.PLANNING: [
            r"\b(architect|plan|design.*system|design.*architecture|roadmap)\b",
            r"\b(strategy|approach|method|process|workflow)\b",
        ],
        TaskType.REFACTORING: [
            r"\b(refactor|restructure|redesign|clean\s+up|tidy|consolidate)\b",
        ],
        TaskType.DOCUMENTATION: [
            r"\b(docs?|documentation|readme|docstring|docblock|comment)\b",
        ],
        TaskType.OPTIMIZATION: [
            r"\b(optimize|performance|fast|speed|accelerate|latency|throughput)\b",
            r"\b(benchmark|profiling|memory\s+use|cpu\s+use)\b",
        ],
        TaskType.TESTING: [
            r"\b(test|testing|unit\s+test|integration\s+test|spec)\b",
            r"\b(assert|expect|assertion|test\s+case|test\s+file)\b",
        ],
    }

    def classify(self, text: str) -> TaskProfile:
        """Classify a task description into complexity and type."""
        complexity = self._classify_complexity(text)
        task_type = self._classify_type(text)
        return TaskProfile(
            text=text,
            complexity=complexity,
            task_type=task_type,
        )

    def _classify_complexity(self, text: str) -> TaskComplexity:
        """Classify task complexity based on keywords."""
        text_lower = text.lower()

        # Check from most specific to least specific
        for complexity in [TaskComplexity.EXPERT, TaskComplexity.COMPLEX,
                          TaskComplexity.MODERATE, TaskComplexity.TRIVIAL, TaskComplexity.SIMPLE]:
            patterns = self.COMPLEXITY_PATTERNS.get(complexity, [])
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return complexity

        return TaskComplexity.SIMPLE  # Default

    def _classify_type(self, text: str) -> TaskType:
        """Classify task type based on keywords."""
        text_lower = text.lower()

        for task_type, patterns in self.TASK_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return task_type

        return TaskType.CODE_GENERATION  # Default


class Router:
    """Main router engine that selects the best provider for each task."""

    def __init__(
        self,
        providers: list[ProviderProfile] | None = None,
        strategy: RoutingStrategy = RoutingStrategy.BALANCED,
        classifier: TaskClassifier | None = None,
    ):
        self.providers = providers or []
        self.strategy = strategy
        self.classifier = classifier or TaskClassifier()
        self._task_history: list[dict] = []

    def add_provider(self, provider: ProviderProfile) -> None:
        """Add a provider to the routing pool."""
        self.providers.append(provider)

    def route(self, task_text: str) -> dict[str, Any]:
        """
        Route a task to the best provider.

        Returns dict with: provider, model, estimated_cost, estimated_latency,
                         task_complexity, task_type, reasoning
        """
        profile = self.classifier.classify(task_text)

        # Score all providers
        scores = []
        for provider in self.providers:
            score = self._score_provider(provider, profile)
            scores.append((provider, score))

        # Select best provider
        scores.sort(key=lambda x: x[1], reverse=True)
        best_provider, best_score = scores[0]

        # Estimate actual costs
        estimated_cost = best_provider.estimated_cost
        estimated_latency = best_provider.estimated_latency

        result = {
            "provider": best_provider.name,
            "model": best_provider.model,
            "task_complexity": profile.complexity.value,
            "task_type": profile.task_type.value,
            "estimated_cost": round(estimated_cost, 6),
            "estimated_latency": round(estimated_latency, 2),
            "score": round(best_score, 3),
            "reasoning": self._generate_reasoning(profile, best_provider, scores),
        }

        self._task_history.append(result)
        logger.info("Routed task (%s → %s) cost=%.4f latency=%.1fs",
                     profile.complexity.value, best_provider.model,
                     estimated_cost, estimated_latency)

        return result

    def route_batch(self, task_texts: list[str]) -> list[dict[str, Any]]:
        """Route multiple tasks."""
        return [self.route(text) for text in task_texts]

    def _score_provider(self, provider: ProviderProfile, profile: TaskProfile) -> float:
        """Score a provider for a given task (higher = better)."""

        # Strategy weights
        if self.strategy == RoutingStrategy.COST_OPTIMIZED:
            weights = {"cost": 0.5, "speed": 0.2, "quality": 0.2, "reliability": 0.1}
        elif self.strategy == RoutingStrategy.SPEED_OPTIMIZED:
            weights = {"cost": 0.1, "speed": 0.5, "quality": 0.2, "reliability": 0.2}
        elif self.strategy == RoutingStrategy.QUALITY_OPTIMIZED:
            weights = {"cost": 0.0, "speed": 0.1, "quality": 0.7, "reliability": 0.2}
        else:  # BALANCED
            weights = {"cost": 0.3, "speed": 0.2, "quality": 0.35, "reliability": 0.15}

        # Cost score (0-1, lower cost = higher score)
        cost_ratio = provider.estimated_cost / max(
            (p.estimated_cost for p in self.providers), default=1.0)
        cost_score = max(0.0, 1.0 - cost_ratio)

        # Speed score (0-1, faster = higher score)
        max_speed = max((p.tokens_per_second for p in self.providers), default=1.0)
        speed_score = provider.tokens_per_second / max_speed if max_speed > 0 else 0

        # Quality score (already 0-1)
        quality_score = provider.quality_score

        # Reliability score (already 0-1)
        reliability_score = provider.reliability_score

        # Complexity fit — adjust quality score based on match
        complexity_quality_map = {
            TaskComplexity.TRIVIAL: 0.8,
            TaskComplexity.SIMPLE: 0.85,
            TaskComplexity.MODERATE: 0.9,
            TaskComplexity.COMPLEX: 0.95,
            TaskComplexity.EXPERT: 1.0,
        }

        # Penalize if provider can't handle context window
        context_penalty = 0.0
        if profile.token_count > provider.max_recommended_context:
            context_penalty = 0.3  # Heavy penalty for exceeding recommended window

        final_score = (
            weights["cost"] * cost_score +
            weights["speed"] * speed_score +
            weights["quality"] * quality_score * complexity_quality_map.get(profile.complexity, 0.8) +
            weights["reliability"] * reliability_score -
            context_penalty
        )

        return final_score

    def _generate_reasoning(
        self, profile: TaskProfile, best: ProviderProfile, all_scores: list[tuple]
    ) -> str:
        """Generate human-readable reasoning for the routing decision."""
        reasons = []

        if profile.complexity == TaskComplexity.TRIVIAL:
            reasons.append("Simple task")
        elif profile.complexity == TaskComplexity.SIMPLE:
            reasons.append("Simple/moderate task")
        elif profile.complexity == TaskComplexity.COMPLEX:
            reasons.append("Complex task requiring strong model")
        elif profile.complexity == TaskComplexity.EXPERT:
            reasons.append("Expert-level task, best model needed")

        if best.cost_per_token == 0:
            reasons.append("local/cheapest option selected")
        elif best.quality_score < 0.8:
            reasons.append("cost-optimized model")
        else:
            reasons.append("balanced quality/cost")

        return " → ".join(reasons)

    @property
    def task_history(self) -> list[dict]:
        """Return routing history."""
        return list(self._task_history)

    def get_cost_report(self) -> dict[str, Any]:
        """Generate cost report from routing history."""
        if not self._task_history:
            return {"total_tasks": 0, "total_cost": 0.0, "average_cost": 0.0}

        total_cost = sum(r["estimated_cost"] for r in self._task_history)
        avg_cost = total_cost / len(self._task_history)

        provider_costs: dict[str, float] = {}
        for r in self._task_history:
            provider_costs[r["provider"]] = provider_costs.get(r["provider"], 0) + r["estimated_cost"]

        return {
            "total_tasks": len(self._task_history),
            "total_cost": round(total_cost, 4),
            "average_cost": round(avg_cost, 6),
            "provider_costs": {
                k: round(v, 4) for k, v in sorted(provider_costs.items(), key=lambda x: x[1], reverse=True)
            },
        }
