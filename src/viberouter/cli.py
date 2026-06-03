"""CLI interface for VibeRouter."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from .router import Router, RoutingStrategy, TaskProfile
from .providers import default_providers

console = Console()


@click.group()
@click.version_option(version="1.0.0", prog_name="VibeRouter")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
def main(verbose: bool) -> None:
    """VibeRouter — AI Coding Agent Router

    Route coding tasks to the optimal model/provider for best cost-quality-speed balance.

    Examples:

    \b
        # Quick route a task
        viberouter "Write a FastAPI endpoint"

        # Route with specific strategy
        viberouter --strategy speed "Debug this error"

        # Show cost report
        viberouter cost-report

        # Interactive mode
        viberouter --interactive
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)


@main.command()
@click.argument("task", type=str)
@click.option(
    "--strategy",
    type=click.Choice(["cost_optimized", "speed_optimized", "quality_optimized", "balanced"]),
    default="balanced",
    help="Routing strategy",
)
@click.option("--json", is_flag=True, help="Output as JSON")
def route(task: str, strategy: str, json_output: bool) -> None:
    """Route a task to the best provider."""
    router = Router(
        providers=default_providers(),
        strategy=RoutingStrategy(strategy),
    )

    result = router.route(task)

    if json_output:
        click.echo(json.dumps(result, indent=2))
        return

    # Pretty print
    rprint(f"\n[bold]🚀 VibeRouter Result[/bold]")
    rprint(f"   Task: [cyan]{task}[/cyan]")
    rprint(f"   Strategy: [magenta]{strategy}[/magenta]")
    rprint()

    table = Table(title="Selected Provider")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Provider", result["provider"])
    table.add_row("Model", result["model"])
    table.add_row("Complexity", result["task_complexity"])
    table.add_row("Task Type", result["task_type"])
    table.add_row("Est. Cost", f"${result['estimated_cost']:.6f}")
    table.add_row("Est. Latency", f"{result['estimated_latency']:.2f}s")
    table.add_row("Score", f"{result['score']:.3f}")

    console.print(table)

    if result["reasoning"]:
        rprint(f"\n[bold]💡 Reasoning:[/bold] {result['reasoning']}")

    # Show top 3 alternatives
    alt_router = Router(
        providers=default_providers(),
        strategy=RoutingStrategy(strategy),
    )
    results = alt_router.route_batch([task])
    if results:
        top = results[0]
        rprint(f"\n[dim]Top alternative: {top['provider']}/{top['model']} (cost: ${top['estimated_cost']:.6f})[/dim]")


@main.command()
@click.option(
    "--last",
    type=int,
    default=5,
    help="Number of tasks to show",
)
@click.option("--json", is_flag=True, help="Output as JSON")
def history(last: int, json_output: bool) -> None:
    """Show routing history."""
    # Load history from file if exists
    history_file = Path.home() / ".viberouter" / "history.json"

    if not history_file.exists():
        console.print("[dim]No history found. Use 'viberoute' first.[/dim]")
        return

    history_data = json.loads(history_file.read_text())

    if json_output:
        click.echo(json.dumps(history_data, indent=2))
        return

    table = Table(title="Routing History (last {})".format(last))
    table.add_column("Task", style="cyan")
    table.add_column("Provider", style="green")
    table.add_column("Model", style="yellow")
    table.add_column("Cost", style="magenta")
    table.add_column("Latency", style="blue")

    for item in history_data[-last:]:
        table.add_row(
            item.get("task", "?")[:30],
            item.get("provider", "?"),
            item.get("model", "?")[:15],
            f"${item.get('cost', 0):.4f}",
            f"{item.get('latency', 0):.1f}s",
        )

    console.print(table)


@main.command()
@click.option(
    "--strategy",
    type=click.Choice(["cost_optimized", "speed_optimized", "quality_optimized", "balanced"]),
    default="balanced",
)
@click.option("--output", type=click.Path(), help="Output file")
def cost_report(strategy: str, output: str | None) -> None:
    """Generate a cost optimization report."""
    router = Router(
        providers=default_providers(),
        strategy=RoutingStrategy(strategy),
    )

    report = router.get_cost_report()

    if output:
        Path(output).write_text(json.dumps(report, indent=2))
        console.print(f"[green]Report saved to {output}[/green]")
        return

    console.print(f"[bold]💰 Cost Report (Strategy: {strategy})[/bold]\n")

    table = Table()
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Total Tasks", str(report["total_tasks"]))
    table.add_row("Total Cost", f"${report['total_cost']:.4f}")
    table.add_row("Average Cost/Task", f"${report['average_cost']:.6f}")

    console.print(table)

    if "provider_costs" in report and report["provider_costs"]:
        console.print("\n[bold]Cost by Provider:[/bold]")
        for provider, cost in report["provider_costs"].items():
            percentage = (cost / report["total_cost"] * 100) if report["total_cost"] > 0 else 0
            console.print(f"  • {provider}: ${cost:.4f} ({percentage:.1f}%)")

    if report["total_tasks"] == 0:
        console.print("\n[dim]No tasks routed yet. Use 'viberoute' to start.[/dim]")


@main.command()
def interactive() -> None:
    """Interactive mode — route tasks continuously."""
    console.print("[bold]🚀 VibeRouter Interactive Mode[/bold]")
    console.print("[dim]Type your coding task or 'quit' to exit[/dim]\n")

    router = Router(
        providers=default_providers(),
        strategy=RoutingStrategy.BALANCED,
    )

    while True:
        try:
            task = console.input("[cyan]Task: [/cyan]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye![/dim]")
            break

        if not task or task.lower() in ("quit", "exit", "q"):
            console.print("[dim]Goodbye![/dim]")
            break

        result = router.route(task)

        table = Table(title="Route Result")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Provider", result["provider"])
        table.add_row("Model", result["model"])
        table.add_row("Complexity", result["task_complexity"])
        table.add_row("Cost", f"${result['estimated_cost']:.6f}")
        table.add_row("Latency", f"{result['estimated_latency']:.2f}s")
        console.print(table)

        if result["reasoning"]:
            console.print(f"[dim]Reasoning: {result['reasoning']}[/dim]\n")


@main.command()
def providers() -> None:
    """List all available providers and their specs."""
    providers_list = default_providers()

    table = Table(title="Available Providers")
    table.add_column("Name", style="cyan")
    table.add_column("Model", style="green")
    table.add_column("Quality", style="yellow")
    table.add_column("Speed (tok/s)", style="blue")
    table.add_column("Cost/Task", style="magenta")

    for p in providers_list:
        table.add_row(
            p.name,
            p.model,
            f"{p.quality_score:.2f}",
            f"{p.tokens_per_second:.0f}",
            f"${p.estimated_cost:.6f}",
        )

    console.print(table)


@main.command()
def benchmark() -> None:
    """Run a benchmark across all strategies."""
    test_tasks = [
        "Fix typo in variable name",
        "Write FastAPI endpoint for user login",
        "Refactor database layer to use SQLAlchemy",
        "Debug memory leak in async code",
        "Explain how JWT authentication works",
        "Create unit tests for authentication module",
        "Optimize SQL query for 1M rows",
        "Write documentation for REST API",
        "Implement OAuth2 login flow",
        "Design microservices architecture",
    ]

    console.print("[bold]🏁 Running Benchmark[/bold]\n")

    for strategy_name in RoutingStrategy:
        console.print(f"\n[dim]Strategy: {strategy_name.value}[/dim]")
        router = Router(
            providers=default_providers(),
            strategy=strategy_name,
        )

        results = router.route_batch(test_tasks)
        total_cost = sum(r["estimated_cost"] for r in results)
        avg_latency = sum(r["estimated_latency"] for r in results) / len(results)

        console.print(f"  Total cost: ${total_cost:.4f} ({len(test_tasks)} tasks)")
        console.print(f"  Avg latency: {avg_latency:.2f}s")

        # Most common provider
        provider_counts = {}
        for r in results:
            provider_counts[r["provider"]] = provider_counts.get(r["provider"], 0) + 1

        most_used = max(provider_counts.items(), key=lambda x: x[1])
        console.print(f"  Most used: {most_used[0]} ({most_used[1]} times)")

        if strategy_name == RoutingStrategy.BALANCED:
            balanced_cost = total_cost
            balanced_latency = avg_latency


if __name__ == "__main__":
    main()
