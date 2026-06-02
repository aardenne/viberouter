"""VibeRouter package — Intelligent LLM Router for multi-node setups."""

__version__ = "0.5.0"
__author__ = "4R Consultancy"

from .core import VibeRouter, CircuitBreaker, AuditEntry, ModelType
from .config import NodeConfig, RouterConfig
from .llm_interface import LLMClient
from .gb10_config import detect_local_gpus, generate_config

__all__ = [
    "VibeRouter",
    "CircuitBreaker",
    "AuditEntry",
    "ModelType",
    "NodeConfig",
    "RouterConfig",
    "LLMClient",
    "detect_local_gpus",
    "generate_config",
]
