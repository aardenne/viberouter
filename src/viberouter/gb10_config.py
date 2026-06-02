"""GB10 auto-configuration helper — generates config from local GPU setup."""

import yaml
import socket
from pathlib import Path
from typing import List, Dict, Optional


def detect_local_gpus() -> List[Dict]:
    """Attempt to detect GB10 nodes on the local network."""
    # Common GB10 IPs on typical LAN
    candidates = [
        ("gb10-1", "192.168.1.10", 30000, "Qwen3-Nemotron"),   # Vision / Latency
        ("gb10-2", "192.168.1.11", 8081, "Qwen3.6-35B-A3B"),   # Coding / Heavy
        ("localhost", "localhost", 30000, "Qwen3-Nemotron"),   # Local fallback
        ("localhost", "localhost", 8081, "Qwen3.6-35B-A3B"),   # Local fallback
    ]

    nodes = []
    for name, host, port, model in candidates:
        try:
            with socket.create_connection((host, port), timeout=2):
                weight = 3 if "35B" in model else 2
                nodes.append({
                    "name": f"{name}-local",
                    "url": f"http://{host}:{port}",
                    "model": model,
                    "weight": weight,
                    "max_connections": 8,
                    "health_check_interval": 15,
                    "timeout": 60,
                })
        except (socket.timeout, ConnectionRefusedError, OSError):
            pass  # Node not available

    return nodes


def generate_config(yaml_path: str = "config.yaml") -> str:
    """Generate a config.yaml from detected nodes."""
    nodes = detect_local_gpus()

    config = {
        "log_level": "INFO",
        "metrics_port": 9090,
        "dashboard_port": 8080,
        "strategy": "type_preferred",
        "fallback_enabled": True,
        "fallback_threshold": 3,
        "nodes": nodes,
    }

    config_path = Path(yaml_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    return f"Config written to {yaml_path} with {len(nodes)} nodes"


if __name__ == "__main__":
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    console.print("[bold cyan]🔍 Detecting GB10 nodes...[/bold cyan]")

    nodes = detect_local_gpus()
    if nodes:
        console.print(f"[bold green]✅ Found {len(nodes)} node(s)[/bold green]")
        for node in nodes:
            console.print(f"  • {node['name']}: {node['url']} ({node['model']})")

        result = generate_config()
        console.print(f"\n{Panel.fit(f'[green]📝 {result}[/green]')}")
    else:
        console.print("[bold yellow]⚠️  No local nodes detected. Use config.yaml.example as template.[/bold yellow]")
