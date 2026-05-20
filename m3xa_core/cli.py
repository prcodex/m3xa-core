"""m3xa CLI entry point.

Commands:
  m3xa query "..."          run the pipeline against a query
  m3xa expertises           list registered expertises
  m3xa healthcheck          report self-awareness component status
  m3xa scrapers             list available scraper templates
"""
from __future__ import annotations

import os

import typer
from rich.console import Console

app = typer.Typer(help="m3xa-core — didactic reference for the House pattern")
console = Console()


@app.command()
def query(
    query: str = typer.Argument(..., help="Query to run through the pipeline"),
    lancedb: str = typer.Option("./examples/sample_corpus", help="LanceDB path"),
    debug: bool = typer.Option(False, help="Print intermediate actor outputs"),
) -> None:
    """Run a query through the 7-actor pipeline."""
    # Lazy import so `m3xa --help` works without backends installed.
    from m3xa_core import Pipeline

    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[red]ANTHROPIC_API_KEY not set.[/red]")
        raise typer.Exit(1)
    if not os.environ.get("VOYAGE_API_KEY"):
        console.print("[red]VOYAGE_API_KEY not set.[/red]")
        raise typer.Exit(1)

    pipeline = Pipeline(lancedb_path=lancedb)
    try:
        result = pipeline.run(query)
    except NotImplementedError as e:
        console.print(f"[yellow]Pipeline skeleton:[/yellow] {e}")
        raise typer.Exit(2) from e

    console.print(result.response)
    console.print(f"\n[dim]Score: {result.score:.1f}/10.0 · "
                  f"Loaded: {result.routing_decision.expertises} · "
                  f"System tokens: {result.estimated_system_tokens}[/dim]")


@app.command()
def expertises() -> None:
    """List all registered expertises from expertises/."""
    from pathlib import Path

    exp_dir = Path(__file__).resolve().parent.parent / "expertises"
    if not exp_dir.exists():
        console.print("[yellow]No expertises/ directory.[/yellow]")
        return
    for p in sorted(exp_dir.glob("*.md")):
        console.print(f"  • {p.stem}")


@app.command()
def healthcheck() -> None:
    """Report on the nine self-awareness components."""
    console.print("[bold]Self-awareness components[/bold]")
    console.print("  (skeleton — not yet wired in v0.1)")
    console.print("  See concepts/self_awareness_loop.md for the design.")


@app.command()
def scrapers() -> None:
    """List the scraper templates."""
    from pathlib import Path

    sc_dir = Path(__file__).resolve().parent / "scrapers"
    for p in sorted(sc_dir.glob("*_template.py")):
        console.print(f"  • {p.stem}")


if __name__ == "__main__":
    app()
