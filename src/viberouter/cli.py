"""VibeRouter CLI interface."""

import typer
import asyncio
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from .core import VibeRouter
from .config import RouterConfig

app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})
console = Console()

def get_router() -> VibeRouter:
    """Get router instance from config."""
    config = RouterConfig()
    return VibeRouter(config)

@app.command()
def status():
    """Show current node status and health."""
    router = get_router()
    status_data = router.get_status()
    
    console.print(Panel.fit("[bold blue]VibeRouter Status[/bold blue]"))
    
    table = Table(title="Node Details")
    table.add_column("Node", style="cyan")
    table.add_column("Model", style="green")
    table.add_column("Status", style="magenta")
    table.add_column("Load", style="yellow")
    table.add_column("Requests", style="blue")
    table.add_column("Errors", style="red")
    
    for name, info in status_data["nodes"].items():
        status_str = "[green]Healthy[/green]" if info["healthy"] else "[red]Unhealthy[/red]"
        table.add_row(
            name,
            info["model"],
            status_str,
            f"{info['load']}/{info['total_capacity']}",
            str(info["requests"]),
            str(info["errors"])
        )
    
    console.print(table)
    console.print(f"\nStrategy: {status_data['strategy']}")
    console.print(f"Healthy: {status_data['healthy_count']}/{status_data['total_nodes']}")

@app.command()
def route(prompt: str):
    """Route a prompt to the best model."""
    router = get_router()
    result = router.route(prompt)
    
    if "error" in result:
        console.print(f"[bold red]❌ Error:[/bold red] {result['error']}")
        return
    
    console.print(Panel.fit(f"[bold green]✅ Routed to {result['node']}[/bold green]"))
    console.print(f"Model: {result['model']}")
    console.print(f"Task Type: {result['task_type']}")
    console.print(f"Current Load: {result['load']}/{result['total_capacity']}")

@app.command()
def health():
    """Run health checks on all nodes."""
    router = get_router()
    asyncio.run(router.initialize())
    console.print("[bold green]✅ Health checks completed![/bold green]")
    router.status()

@app.command()
def config():
    """Show current configuration."""
    config = RouterConfig()
    console.print(Panel.fit("[bold cyan]Current Configuration[/bold cyan]"))
    console.print(f"Log Level: {config.log_level}")
    console.print(f"Metrics Port: {config.metrics_port}")
    console.print(f"Strategy: {config.strategy}")
    console.print(f"Nodes: {len(config.nodes)}")
    
    for node in config.nodes:
        console.print(f"\n  [bold]• {node.name}[/bold]")
        console.print(f"    URL: {node.url}")
        console.print(f"    Model: {node.model}")
        console.print(f"    Weight: {node.weight}")

@app.command()
def benchmark():
    """Run a quick benchmark of all nodes."""
    console.print("[bold yellow]Running benchmark...[/bold yellow]")
    router = get_router()
    asyncio.run(router.initialize())
    
    # Simple benchmark with a test prompt
    test_prompt = "Write a Python function to calculate fibonacci numbers recursively."
    
    for name, client in router.clients.items():
        try:
            import time
            start = time.time()
            client.node.max_connections = 1  # Limit for benchmark
            result = router.route(test_prompt)
            latency = time.time() - start
            router.release_load(name)
            
            console.print(f"  ✅ {name}: {latency:.2f}s - {result.get('model', 'N/A')}")
        except Exception as e:
            console.print(f"  ❌ {name}: {str(e)}")

if __name__ == "__main__":
    app()
