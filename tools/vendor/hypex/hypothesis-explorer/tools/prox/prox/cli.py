"""CLI entry-point for the prox tool."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import click

for _req_pkg in ("numpy", "scipy", "sklearn", "networkx"):
    if importlib.util.find_spec(_req_pkg) is None:
        raise ModuleNotFoundError(f"No module named '{_req_pkg}'")


@click.group()
def main() -> None:
    """prox -- proximity / similarity tool for Hypothesis-Explorer."""


@main.command()
@click.option(
    "--run-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Path to the run directory containing hypotheses/.",
)
@click.option(
    "--backend",
    default="tfidf",
    type=click.Choice(["tfidf", "sbert"]),
    help="Embedding backend (default: tfidf).",
)
def embed(run_dir: Path, backend: str) -> None:
    """Vectorise hypothesis texts and write embeddings."""
    from prox.embed import run_embed

    run_embed(run_dir, backend=backend)
    click.echo(f"Embeddings written to {run_dir / 'proximity'}")


@main.command()
@click.option(
    "--run-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Path to the run directory.",
)
@click.option(
    "--threshold",
    default=0.3,
    type=float,
    help="Minimum cosine similarity to create an edge (default: 0.3).",
)
def graph(run_dir: Path, threshold: float) -> None:
    """Build a cosine-similarity adjacency graph from embeddings."""
    from prox.graph import run_graph

    run_graph(run_dir, threshold=threshold)
    click.echo(f"Graph written to {run_dir / 'proximity' / 'graph.json'}")


@main.command()
@click.option(
    "--run-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Path to the run directory.",
)
def clusters(run_dir: Path) -> None:
    """Detect communities and assign cluster labels."""
    from prox.cluster import run_clusters

    run_clusters(run_dir)
    click.echo(f"Clusters written to {run_dir / 'proximity' / 'clusters.json'}")


@main.command()
@click.option(
    "--run-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Path to the run directory.",
)
@click.option(
    "--threshold",
    default=0.80,
    type=float,
    help="Minimum similarity to flag as near-duplicate (default: 0.80).",
)
def dupes(run_dir: Path, threshold: float) -> None:
    """Report near-duplicate hypothesis pairs."""
    from prox.dupes import run_dupes

    output = run_dupes(run_dir, threshold=threshold)
    click.echo(output)
