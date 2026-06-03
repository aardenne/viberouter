"""Provider definitions with real-world benchmarks."""

from __future__ import annotations

from .router import ProviderProfile

# === OpenAI Providers ===

def openai_gpt4o() -> ProviderProfile:
    """OpenAI GPT-4o — Best quality, higher cost."""
    return ProviderProfile(
        name="openai",
        model="gpt-4o",
        cost_per_token=0.0025 / 1_000_000,    # $2.50/M input tokens
        cost_per_output_token=0.01 / 1_000_000,  # $10/M output tokens
        tokens_per_second=80,
        max_context_window=128000,
        max_recommended_context=64000,
        quality_score=0.98,
        reliability_score=0.99,
        latency_p99=3.0,
    )

def openai_gpt4o_mini() -> ProviderProfile:
    """OpenAI GPT-4o Mini — Good balance."""
    return ProviderProfile(
        name="openai",
        model="gpt-4o-mini",
        cost_per_token=0.15 / 1_000_000,
        cost_per_output_token=0.60 / 1_000_000,
        tokens_per_second=100,
        max_context_window=128000,
        max_recommended_context=64000,
        quality_score=0.85,
        reliability_score=0.99,
        latency_p99=2.0,
    )

def openai_gpt4_1106() -> ProviderProfile:
    """OpenAI GPT-4 Turbo — Strong coding ability."""
    return ProviderProfile(
        name="openai",
        model="gpt-4-1106-preview",
        cost_per_token=0.01 / 1_000_000,
        cost_per_output_token=0.03 / 1_000_000,
        tokens_per_second=60,
        max_context_window=128000,
        max_recommended_context=64000,
        quality_score=0.96,
        reliability_score=0.98,
        latency_p99=5.0,
    )

# === Anthropic Providers ===

def anthropic_claude_4_sonnet() -> ProviderProfile:
    """Anthropic Claude 4 Sonnet — Best for coding."""
    return ProviderProfile(
        name="anthropic",
        model="claude-4-sonnet",
        cost_per_token=0.003 / 1_000_000,
        cost_per_output_token=0.015 / 1_000_000,
        tokens_per_second=55,
        max_context_window=200000,
        max_recommended_context=100000,
        quality_score=0.97,
        reliability_score=0.98,
        latency_p99=4.0,
    )

def anthropic_claude_4_haiku() -> ProviderProfile:
    """Anthropic Claude 4 Haiku — Fast, cheap."""
    return ProviderProfile(
        name="anthropic",
        model="claude-4-haiku",
        cost_per_token=0.0008 / 1_000_000,
        cost_per_output_token=0.004 / 1_000_000,
        tokens_per_second=90,
        max_context_window=200000,
        max_recommended_context=100000,
        quality_score=0.82,
        reliability_score=0.98,
        latency_p99=2.0,
    )

# === OpenRouter Providers ===

def openrouter_llama_3_70b() -> ProviderProfile:
    """Meta Llama 3 70B via OpenRouter — Great open model."""
    return ProviderProfile(
        name="openrouter",
        model="meta-llama/llama-3.1-70b",
        cost_per_token=0.0009 / 1_000_000,
        cost_per_output_token=0.0009 / 1_000_000,
        tokens_per_second=70,
        max_context_window=128000,
        max_recommended_context=64000,
        quality_score=0.90,
        reliability_score=0.95,
        latency_p99=5.0,
    )

def openrouter_gemma_7b() -> ProviderProfile:
    """Google Gemma 7B — Cheap and fast."""
    return ProviderProfile(
        name="openrouter",
        model="google/gemma-2-27b",
        cost_per_token=0.0002 / 1_000_000,
        cost_per_output_token=0.0002 / 1_000_000,
        tokens_per_second=90,
        max_context_window=8192,
        max_recommended_context=4096,
        quality_score=0.75,
        reliability_score=0.96,
        latency_p99=2.0,
    )

def openrouter_mixtral_8x7b() -> ProviderProfile:
    """Mixtral 8x7B — Good MoE balance."""
    return ProviderProfile(
        name="openrouter",
        model="mistralai/mixtral-8x7b",
        cost_per_token=0.00024 / 1_000_000,
        cost_per_output_token=0.00024 / 1_000_000,
        tokens_per_second=85,
        max_context_window=32000,
        max_recommended_context=16000,
        quality_score=0.83,
        reliability_score=0.95,
        latency_p99=3.0,
    )

def openrouter_qwen_2_72b() -> ProviderProfile:
    """Qwen 2 72B — Strong Chinese + English."""
    return ProviderProfile(
        name="openrouter",
        model="qwen/qwen-2-72b",
        cost_per_token=0.00036 / 1_000_000,
        cost_per_output_token=0.00036 / 1_000_000,
        tokens_per_second=65,
        max_context_window=32000,
        max_recommended_context=16000,
        quality_score=0.88,
        reliability_score=0.94,
        latency_p99=6.0,
    )

# === Local Providers ===

def local_qwen3_35b() -> ProviderProfile:
    """Qwen3.6-35B running locally via vLLM (GB10)."""
    return ProviderProfile(
        name="local",
        model="qwen3.6-35b",
        cost_per_token=0,
        cost_per_output_token=0,
        tokens_per_second=75,  # ~75 tok/s on GB10 with NVFP4
        max_context_window=131072,
        max_recommended_context=65536,
        quality_score=0.88,  # Competitive with GPT-4o-mini
        reliability_score=0.97,
        latency_p99=1.0,  # Near-instant for short responses
    )

def local_gemma_4b() -> ProviderProfile:
    """Gemma-4B — Super fast local fallback."""
    return ProviderProfile(
        name="local",
        model="gemma-4b-it",
        cost_per_token=0,
        cost_per_output_token=0,
        tokens_per_second=150,
        max_context_window=8192,
        max_recommended_context=4096,
        quality_score=0.70,
        reliability_score=0.98,
        latency_p99=0.5,
    )

# === Pre-built provider lists ===

def default_providers() -> list[ProviderProfile]:
    """Get a sensible default provider pool."""
    return [
        local_qwen3_35b(),
        openai_gpt4o_mini(),
        openrouter_llama_3_70b(),
        openrouter_gemma_7b(),
        local_gemma_4b(),
        openai_gpt4o(),
        anthropic_claude_4_haiku(),
    ]

def minimal_providers() -> list[ProviderProfile]:
    """Minimal setup: one local + one cloud."""
    return [
        local_qwen3_35b(),
        openai_gpt4o_mini(),
    ]
