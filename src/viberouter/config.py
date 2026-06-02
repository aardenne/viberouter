"""Configuration management for VibeRouter."""

from typing import Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NodeConfig(BaseModel):
    """Configuration for an LLM node."""
    name: str = Field(description="Unique name for the node")
    url: str = Field(description="Base URL of the LLM API")
    model: str = Field(description="Model name to use")
    weight: int = Field(default=1, description="Weight for load balancing (higher = more traffic)")
    health_check_interval: int = Field(default=30, description="Seconds between health checks")
    max_connections: int = Field(default=10, description="Max concurrent connections")
    timeout: int = Field(default=60, description="Request timeout in seconds")
    api_key: Optional[str] = Field(default=None, description="API key if required")


class RouterConfig(BaseSettings):
    """Main configuration for the router."""
    model_config = SettingsConfigDict(env_prefix="VIBEROUTER_", yaml_file="config.yaml")

    # Global settings
    log_level: str = "INFO"
    metrics_port: int = 9090
    dashboard_port: int = 8080

    # Node configurations
    nodes: list[NodeConfig] = []

    # Routing strategy: 'weighted_round_robin', 'least_connections', 'least_loaded'
    strategy: str = "weighted_round_robin"

    # Auto-fallback settings
    fallback_enabled: bool = True
    fallback_threshold: int = 3  # Number of consecutive failures before marking node unhealthy
