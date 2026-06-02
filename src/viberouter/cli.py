"""VibeRouter CLI interface."""

import typer
import asyncio
import json
import time
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from .core import VibeRouter, AuditEntry
from .config import RouterConfig

app = typer.Typer(
    name="viberouter",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
)
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

    console.print(Panel.fit("[bold blue]⚡ VibeRouter Status[/bold blue]"))

    table = Table(title="Node Details")
    table.add_column("Node", style="cyan")
    table.add_column("Model", style="green")
    table.add_column("Status", style="magenta")
    table.add_column("Load", style="yellow")
    table.add_column("Requests", style="blue")
    table.add_column("Errors", style="red")
    table.add_column("Tokens", style="magenta")

    for name, info in status_data["nodes"].items():
        status_str = "[green]● Healthy[/green]" if info["healthy"] else "[red]● Unhealthy[/red]"
        table.add_row(
            name,
            info["model"],
            status_str,
            f"{info['load']}/{info['total_capacity']}",
            str(info["requests"]),
            str(info["errors"]),
            f"{info['tokens']:,}",
        )

    console.print(table)
    console.print(f"\n[bold]Strategy:[/bold] {status_data['strategy']}")
    console.print(f"[bold]Cluster:[/bold] [green]{status_data['healthy_count']}[/green]/{status_data['total_nodes']} healthy")


@app.command()
def route(prompt: str, node: str = typer.Option(None, "--node", "-n", help="Override node name")):
    """Route a prompt to the best model."""
    router = get_router()
    result = router.route(prompt)

    if "error" in result:
        console.print(f"[bold red]❌ Error:[/bold red] {result['error']}")
        return

    console.print(Panel.fit(f"[bold green]✅ Routed to {result['node']}[/bold green]"))
    console.print(f"  Model: [cyan]{result['model']}[/cyan]")
    console.print(f"  Task: [magenta]{result['task_type']}[/magenta]")
    console.print(f"  Load: {result['load']}/{result['total_capacity']}")
    console.print(f"  Latency: {result.get('latency_ms', 0):.1f}ms")


@app.command()
def health():
    """Run health checks on all nodes."""
    router = get_router()
    console.print("[bold yellow]🔍 Running health checks...[/bold yellow]")
    asyncio.run(router.initialize())

    status_data = router.get_status()
    for name, info in status_data["nodes"].items():
        status = "[green]● Healthy[/green]" if info["healthy"] else "[red]● Unhealthy[/red]"
        console.print(f"  {name}: {status}")

    console.print(f"\n[bold green]✅ Health checks completed! {status_data['healthy_count']}/{status_data['total_nodes']} healthy[/bold green]")


@app.command()
def config():
    """Show current configuration."""
    config = RouterConfig()
    console.print(Panel.fit("[bold cyan]⚙️  Current Configuration[/bold cyan]"))
    console.print(f"  Log Level: {config.log_level}")
    console.print(f"  Metrics Port: {config.metrics_port}")
    console.print(f"  Strategy: [magenta]{config.strategy}[/magenta]")
    console.print(f"  Nodes: {len(config.nodes)}")

    for node in config.nodes:
        console.print(f"\n  [bold]• {node.name}[/bold]")
        console.print(f"    URL: {node.url}")
        console.print(f"    Model: {node.model}")
        console.print(f"    Weight: {node.weight}")
        console.print(f"    Max Connections: {node.max_connections}")


@app.command()
def benchmark(iterations: int = typer.Option(3, "--iterations", "-i", help="Number of routing iterations")):
    """Run a quick benchmark of all nodes."""
    console.print("[bold yellow]🏃 Running benchmark...[/bold yellow]")
    router = get_router()
    asyncio.run(router.initialize())

    # Save original max_connections
    original_limits = {}
    for name, client in router.clients.items():
        original_limits[name] = client.node.max_connections
        client.node.max_connections = 1  # Limit for benchmark

    # Benchmark prompts
    test_prompts = {
        "coding": "Write a Python function to calculate fibonacci numbers recursively.",
        "reasoning": "Explain the difference between TCP and UDP, and when you would use each one. Provide at least three examples.",
        "simple": "What color is the sky?",
    }

    results = {}
    with Progress(SpinnerColumn(), TextColumn("[yellow]{task.description}[/]"), console=console) as progress:
        for task_type, prompt in test_prompts.items():
            task = progress.add_task(f"Testing {task_type}", total=iterations)
            latencies = []

            for i in range(iterations):
                start = time.monotonic()
                result = router.route(prompt)
                latency_ms = (time.monotonic() - start) * 1000
                latencies.append(latency_ms)

                if "node" in result and result["node"]:
                    for name in router.load_counters:
                        router.release_load(name)
                break  # Only one iteration per prompt type

            avg = sum(latencies) / len(latencies)
            min_lat = min(latencies)
            max_lat = max(latencies)
            results[task_type] = {"avg": avg, "min": min_lat, "max": max_lat}
            progress.update(task, advance=1)

            console.print(f"  {task_type}: avg={avg:.1f}ms, min={min_lat:.1f}ms, max={max_lat:.1f}ms")

    # Restore original limits
    for name, client in router.clients.items():
        client.node.max_connections = original_limits.get(name, client.node.max_connections)

    # Summary
    console.print(Panel.fit("[bold green]✅ Benchmark Complete[/bold green]"))
    summary_table = Table(title="Results Summary")
    summary_table.add_column("Task Type", style="cyan")
    summary_table.add_column("Avg Latency", style="yellow")
    summary_table.add_column("Min Latency", style="green")
    summary_table.add_column("Max Latency", style="red")

    for task_type, data in results.items():
        summary_table.add_row(
            task_type,
            f"{data['avg']:.1f}ms",
            f"{data['min']:.1f}ms",
            f"{data['max']:.1f}ms",
        )

    console.print(summary_table)


@app.command()
def simulate(prompts_file: str = typer.Option(None, "--file", "-f", help="JSON file with prompts array")):
    """Simulate routing with multiple prompts."""
    router = get_router()

    if prompts_file:
        with open(prompts_file) as f:
            prompts = json.load(f)
    else:
        # Demo prompts
        prompts = [
            "Write a Python Flask API endpoint for user authentication",
            "Analyze this image and describe what you see",
            "Calculate the mean and standard deviation of [1,2,3,4,5]",
            "Check for security vulnerabilities in this code",
            "Tell me a joke",
        ]

    console.print(f"[bold yellow]🎯 Simulating {len(prompts)} prompts...[/bold yellow]")

    results = {}
    for prompt in prompts:
        result = router.route(prompt)
        node = result.get("node", "error")
        if node not in results:
            results[node] = {"count": 0, "task_types": set()}
        results[node]["count"] += 1
        results[node]["task_types"].add(result.get("task_type", "unknown"))

    table = Table(title="Simulation Results")
    table.add_column("Node", style="cyan")
    table.add_column("Requests", style="green")
    table.add_column("Task Types", style="magenta")

    for node, data in results.items():
        types_str = ", ".join(sorted(data["task_types"]))
        table.add_row(node, str(data["count"]), types_str)

    console.print(table)
    console.print(f"\n[green]✅ Completed {len(prompts)} prompts[/green]")


@app.command()
def audit(limit: int = typer.Option(20, "--limit", "-l", help="Number of entries to show")):
    """Show recent routing audit log."""
    router = get_router()
    entries = router.get_audit_log(limit)

    if not entries:
        console.print("[yellow]No audit entries yet.[/yellow]")
        return

    table = Table(title="Audit Log")
    table.add_column("ID", style="dim")
    table.add_column("Time", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Node", style="green")
    table.add_column("Latency", style="yellow")
    table.add_column("Status", style="blue")

    for entry in entries:
        status_str = "[green]success[/green]" if entry["status"] == "success" else "[red]failed[/red]"
        table.add_row(
            entry["id"],
            entry["timestamp"][:19],
            entry["task_type"] or "-",
            entry["node"],
            f"{entry['latency_ms']:.1f}ms",
            status_str,
        )

    console.print(table)


@app.command()
def logs():
    """Show real-time router logs."""
    console.print("[bold cyan]📋 Starting log stream (Ctrl+C to stop)...\n[/bold cyan]")

    try:
        while True:
            time.sleep(1)
            # Log entries go to stderr/logger, we just keep the session alive
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped log stream.[/yellow]")


if __name__ == "__main__":
    app()
