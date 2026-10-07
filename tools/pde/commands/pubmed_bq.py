"""`pde pubmed-bq` -- PubMed literature search via SQL Warehouse.

Where `pubmed` queries NCBI E-utilities (keyword search, limited to 100
results per call), this tool queries the PubMed dataset hosted on a SQL
Warehouse, enabling SQL-based filtering with larger result sets, date
range filters, and journal filters.

Two phases:

  search   queries the SQL Warehouse PubMed table and writes verbatim results
           to Layer 0 with a provenance sidecar.
  analyze  reads those results and produces a summary analysis: year
           distribution, journal distribution, abstract keyword frequency.
           No network.

Like `pubmed`, a SQL warehouse keyword search is inherently non-exhaustive:
SQL substring matching may miss publications using different terminology,
alternate spellings, or synonyms.  The relay
`pubmed_bq.search_not_exhaustive` carries this caveat into the finding
so a report cannot present search results as a complete literature survey.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from typing import Any

import click

from ..common import (
    AppState,
    emitter,
    from_option,
    out_option,
    output_options,
    pass_state,
)
from ..core import provenance
from ..core.errors import ArtifactError, Refusal, SchemaError

TOOL = "pubmed-bq"
ARTIFACT_CLASS = "literature"  # same as pubmed -- both produce literature artifacts

DEFAULT_BQ_DATASET = "public-data.nih_nlm.pubmed"
DEFAULT_TABLE = "publications"

# Columns expected in the SQL Warehouse PubMed table.  If the actual schema
# differs, the query will fail with a SchemaError rather than silently
# returning wrong data.
EXPECTED_COLUMNS = ("pmid", "title", "abstract", "journal", "year", "authors", "doi")

# Common English stop words excluded from abstract keyword analysis.
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "not",
        "no",
        "nor",
        "as",
        "if",
        "then",
        "than",
        "so",
        "up",
        "out",
        "about",
        "into",
        "over",
        "after",
        "we",
        "our",
        "they",
        "their",
        "them",
        "he",
        "she",
        "his",
        "her",
        "which",
        "who",
        "whom",
        "what",
        "when",
        "where",
        "how",
        "all",
        "each",
        "both",
        "more",
        "most",
        "other",
        "some",
        "such",
        "only",
        "also",
        "very",
        "just",
        "because",
        "through",
        "between",
        "before",
        "during",
        "without",
        "within",
        "among",
        "however",
        "while",
        "there",
        "here",
        "using",
        "used",
        "one",
        "two",
        "new",
    }
)


def _slugify(query: str) -> str:
    """Derive a filesystem-safe slug from a search query string."""
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", query).strip("-").lower()
    return slug[:80] or "pubmed-bq-search"


def _get_bq_dataset(override: str | None) -> str:
    """Resolve SQL warehouse dataset: --bq-dataset flag > env var > default."""
    if override:
        return override
    return os.environ.get("PDE_PUBMED_BQ_DATASET", DEFAULT_BQ_DATASET)


def _extract_field(row: Any, field: str) -> Any:
    """Extract a field from a warehouse Row, returning None on missing columns."""
    try:
        return row[field]
    except (KeyError, IndexError, TypeError):
        return None


def _rows_to_articles(rows: Any) -> list[dict[str, Any]]:
    """Convert warehouse result rows to structured article dicts.

    Handles variation in the ``authors`` column: it may be a string
    (comma-separated), a list, a nested structure, or absent entirely.
    """
    articles: list[dict[str, Any]] = []
    for row in rows:
        pmid_raw = _extract_field(row, "pmid")
        pmid = str(pmid_raw) if pmid_raw is not None else None
        if not pmid:
            continue

        year_raw = _extract_field(row, "year")
        year = str(year_raw) if year_raw is not None else None

        authors_raw = _extract_field(row, "authors")
        if isinstance(authors_raw, str):
            authors = [a.strip() for a in authors_raw.split(",") if a.strip()]
        elif isinstance(authors_raw, (list, tuple)):
            authors = [str(a) for a in authors_raw if a]
        else:
            authors = []

        articles.append(
            {
                "pmid": pmid,
                "title": _extract_field(row, "title"),
                "abstract": _extract_field(row, "abstract"),
                "journal": _extract_field(row, "journal"),
                "year": year,
                "authors": authors,
                "doi": _extract_field(row, "doi"),
            }
        )
    return articles


def _validate_identifier(value: str, label: str) -> None:
    """Validate a warehouse identifier (dataset or table name) against injection."""
    if not re.match(r"^[a-zA-Z0-9_.-]+$", value):
        raise SchemaError(
            f"invalid warehouse {label} name",
            detail=f"{label} name contains invalid characters: {value!r}",
            remedy="use only letters, digits, underscores, hyphens, and dots",
        )


def _execute_search(
    dataset: str,
    query: str,
    max_results: int,
    year_from: int | None = None,
    year_to: int | None = None,
    journal: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Execute the warehouse PubMed search and return (articles, query_metadata).

    Raises SchemaError on schema mismatch, Refusal on auth/dataset issues.
    """
    _validate_identifier(dataset, "dataset")
    _validate_identifier(DEFAULT_TABLE, "table")

    try:
        import importlib
        bq_client = importlib.import_module("cloud_bq")
    except ImportError as exc:
        raise SchemaError(
            "cloud-bq package is not available",
            detail=str(exc),
        ) from exc

    terms = query.split()
    if not terms:
        raise Refusal(
            "empty search query",
            remedy="provide at least one search term",
        )

    # Build WHERE clause: each term must appear in title OR abstract.
    where_parts: list[str] = []
    params: list[Any] = []

    for i, term in enumerate(terms):
        pname = f"term_{i}"
        where_parts.append(
            f"(CONTAINS_SUBSTR(COALESCE(title, ''), @{pname}) "
            f"OR CONTAINS_SUBSTR(COALESCE(abstract, ''), @{pname}))"
        )
        params.append(bq_client.ScalarQueryParameter(pname, "STRING", term))

    if year_from is not None:
        where_parts.append("SAFE_CAST(year AS INT64) >= @year_from")
        params.append(bq_client.ScalarQueryParameter("year_from", "INT64", year_from))

    if year_to is not None:
        where_parts.append("SAFE_CAST(year AS INT64) <= @year_to")
        params.append(bq_client.ScalarQueryParameter("year_to", "INT64", year_to))

    if journal is not None:
        where_parts.append("CONTAINS_SUBSTR(COALESCE(journal, ''), @journal_filter)")
        params.append(
            bq_client.ScalarQueryParameter("journal_filter", "STRING", journal)
        )

    params.append(bq_client.ScalarQueryParameter("max_results", "INT64", max_results))

    where_sql = " AND ".join(where_parts)
    table_ref = f"`{dataset}.{DEFAULT_TABLE}`"
    columns = ", ".join(EXPECTED_COLUMNS)

    sql = (
        f"SELECT {columns}\n"
        f"FROM {table_ref}\n"
        f"WHERE {where_sql}\n"
        f"ORDER BY SAFE_CAST(year AS INT64) DESC\n"
        f"LIMIT @max_results"
    )

    job_config = bq_client.QueryJobConfig(query_parameters=params)

    try:
        client = bq_client.Client()
    except Exception as exc:
        raise Refusal(
            "could not initialise SQL warehouse client",
            detail=str(exc),
            remedy=(
                "ensure Application Default Credentials are configured "
                "(run `cloud-auth auth application-default login` or set "
                "CLOUD_APPLICATION_CREDENTIALS)"
            ),
        ) from exc

    try:
        query_job = client.query(sql, job_config=job_config)
        result_rows = query_job.result()
        total_bytes = query_job.total_bytes_processed or 0
    except Exception as exc:
        exc_str = str(exc)
        exc_lower = exc_str.lower()
        # Detect schema mismatches vs other errors.
        if "not found" in exc_lower and ("column" in exc_lower or "field" in exc_lower):
            raise SchemaError(
                "Warehouse PubMed table schema does not match expected columns",
                detail=(
                    f"expected columns: {', '.join(EXPECTED_COLUMNS)}; "
                    f"error: {exc_str[:300]}"
                ),
            ) from exc
        if "not found" in exc_lower and (
            "table" in exc_lower or "dataset" in exc_lower
        ):
            raise Refusal(
                f"Warehouse dataset or table not found: {dataset}.{DEFAULT_TABLE}",
                detail=exc_str[:300],
                remedy=(
                    "check that the dataset exists; override with "
                    "--bq-dataset or $PDE_PUBMED_BQ_DATASET"
                ),
            ) from exc
        raise SchemaError(
            "Warehouse query failed",
            detail=exc_str[:500],
        ) from exc

    articles = _rows_to_articles(result_rows)

    query_meta: dict[str, Any] = {
        "terms": query,
        "max_results": max_results,
        "year_from": year_from,
        "year_to": year_to,
        "journal_filter": journal,
        "dataset": dataset,
        "table": DEFAULT_TABLE,
        "sql": sql,
        "total_bytes_processed": total_bytes,
        "n_results": len(articles),
    }

    return articles, query_meta


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@click.group()
def pubmed_bq() -> None:
    """PubMed literature search via SQL Warehouse."""


@pubmed_bq.command("search")
@click.argument("query")
@click.option(
    "--max-results",
    default=50,
    type=click.IntRange(1, 1000),
    help="Number of results to return (1-1000, default 50).",
)
@click.option(
    "--year-from",
    default=None,
    type=int,
    help="Include only articles published in or after this year.",
)
@click.option(
    "--year-to",
    default=None,
    type=int,
    help="Include only articles published in or before this year.",
)
@click.option(
    "--journal",
    default=None,
    help="Filter by journal name (substring match, case-insensitive).",
)
@click.option(
    "--bq-dataset",
    default=None,
    help=(
        f"SQL warehouse dataset path (default: {DEFAULT_BQ_DATASET}). "
        "Also settable via $PDE_PUBMED_BQ_DATASET."
    ),
)
@out_option
@output_options
@pass_state
def search_cmd(
    state: AppState,
    query: str,
    max_results: int,
    year_from: int | None,
    year_to: int | None,
    journal: str | None,
    bq_dataset: str | None,
    out: str | None,
    as_json: bool,
    quiet: bool,
) -> None:
    """Search PubMed via SQL Warehouse for QUERY and write structured results.

    QUERY is split into terms; each term must appear in the article's
    title or abstract (AND logic).  Use --year-from/--year-to for date
    ranges and --journal for journal filtering.
    """
    emit = emitter(as_json, quiet)
    target_dir = state.project().artifact_dir(ARTIFACT_CLASS, out)

    dataset = _get_bq_dataset(bq_dataset)
    slug = _slugify(query)

    articles, query_meta = _execute_search(
        dataset=dataset,
        query=query,
        max_results=max_results,
        year_from=year_from,
        year_to=year_to,
        journal=journal,
    )

    # Build structured artifact.
    artifact: dict[str, Any] = {
        "schema": "pde.pubmed-bq.v1",
        "query": query_meta,
        "summary": {
            "n_results": len(articles),
            "total_bytes_processed": query_meta.get("total_bytes_processed", 0),
        },
        "results": articles,
    }

    artifact_path = target_dir / f"{slug}.pubmed-bq.json"
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    # Sidecar.
    sidecar = provenance.Sidecar(
        tool=TOOL,
        subcommand="search",
        endpoint="warehouse.ncbi.nlm.nih.gov",
        parameters={
            "query": query,
            "max_results": max_results,
            "year_from": year_from,
            "year_to": year_to,
            "journal_filter": journal,
            "dataset": dataset,
            "table": DEFAULT_TABLE,
        },
    )
    sidecar.note("source", "PubMed via SQL Warehouse (NIH/NLM)")
    sidecar.note("licence", "NLM Terms of Service -- abstracts only")
    sidecar.note("n_results", str(len(articles)))
    sidecar.note("bytes_processed", str(query_meta["total_bytes_processed"]))
    sidecar.note("sql", query_meta["sql"])

    sidecar.add_output(artifact_path)

    meta_path = sidecar.write(target_dir / f"{slug}.pubmed-bq.meta.json")

    # Emit.
    emit.data("query", query)
    emit.data("dataset", dataset)
    emit.data("n_results", len(articles))
    emit.data("bytes_processed", query_meta["total_bytes_processed"])
    emit.path(artifact_path, role="artifact")
    emit.path(meta_path, role="sidecar")
    emit.line(f"PubMed SQL warehouse search: {query!r}")
    emit.line(f"  {len(articles)} results retrieved from {dataset}.{DEFAULT_TABLE}")
    if articles:
        for a in articles[:5]:
            emit.line(f"  PMID {a['pmid']}: {(a.get('title') or '(no title)')[:70]}")
        if len(articles) > 5:
            emit.line(f"  ... {len(articles) - 5} more in the artifact")
    emit.flush()


@pubmed_bq.command("analyze")
@click.argument("query")
@from_option
@out_option
@output_options
@pass_state
def analyze_cmd(
    state: AppState,
    query: str,
    from_dir: str | None,
    out: str | None,
    as_json: bool,
    quiet: bool,
) -> None:
    """Summarise stored PubMed SQL warehouse search results for QUERY. No network.

    Reads what ``search`` wrote and produces a summary analysis: year
    distribution, journal distribution, abstract keyword frequency.
    """
    emit = emitter(as_json, quiet)
    source_dir = state.project().artifact_dir(ARTIFACT_CLASS, from_dir)
    target_dir = state.project().artifact_dir(ARTIFACT_CLASS, out)

    slug = _slugify(query)

    # Locate the structured artifact.
    artifact_path = source_dir / f"{slug}.pubmed-bq.json"
    if not artifact_path.is_file():
        raise ArtifactError(
            f"no PubMed SQL warehouse search artifact for {query!r} under {source_dir}",
            remedy=f"run `pde pubmed-bq search {query!r}` first",
        )

    artifact = provenance.read_json(artifact_path, "PubMed SQL warehouse search artifact")
    if artifact.get("schema") != "pde.pubmed-bq.v1":
        raise SchemaError(
            f"unexpected schema in {artifact_path.name}",
            detail=f"expected pde.pubmed-bq.v1, got {artifact.get('schema')!r}",
        )
    if not isinstance(artifact, dict) or "results" not in artifact:
        raise SchemaError(
            "PubMed SQL warehouse search artifact has no results array",
            detail=(
                f"keys: {list(artifact.keys()) if isinstance(artifact, dict) else type(artifact).__name__}"
            ),
        )

    results = artifact["results"]
    artifact.get("query", {})

    # Compute distributions.
    year_counts: Counter[str] = Counter()
    journal_counts: Counter[str] = Counter()
    keyword_counts: Counter[str] = Counter()

    for r in results:
        year = r.get("year")
        if year:
            year_counts[str(year)] += 1
        journal_name = r.get("journal")
        if journal_name:
            journal_counts[journal_name] += 1
        abstract = r.get("abstract")
        if abstract and isinstance(abstract, str):
            # Simple word-frequency analysis over abstracts.
            words = re.findall(r"[a-z]{3,}", abstract.lower())
            for w in words:
                if w not in _STOP_WORDS:
                    keyword_counts[w] += 1

    outcome = "results_found" if results else "no_results"

    top_journals = journal_counts.most_common(10)
    top_keywords = keyword_counts.most_common(30)
    year_distribution = dict(sorted(year_counts.items()))

    relays: list[dict[str, str]] = []
    if outcome == "results_found":
        relays.append(
            provenance.relay(
                "pubmed_bq.search_not_exhaustive",
                f"PubMed SQL warehouse search for {query!r} returned {len(results)} "
                "results via SQL substring matching; relevant publications may "
                "use different terminology, alternate spellings, or synonyms "
                "not captured by the query terms",
            )
        )

    assessment: dict[str, Any] = {
        "outcome": outcome,
        "query": query,
        "n_retrieved": len(results),
        "year_distribution": year_distribution,
        "top_journals": [{"journal": j, "count": c} for j, c in top_journals],
        "top_abstract_keywords": [{"term": t, "count": c} for t, c in top_keywords],
    }

    metrics: dict[str, Any] = {
        "n_retrieved": len(results),
        "n_unique_journals": len(journal_counts),
        "n_unique_keywords": len(keyword_counts),
        "year_range": [
            min(year_counts) if year_counts else None,
            max(year_counts) if year_counts else None,
        ],
    }

    # Locate the meta file written by search for the source reference.
    meta_path = source_dir / f"{slug}.pubmed-bq.meta.json"
    source_ref = (
        state.project().relative(meta_path)
        if meta_path.is_file()
        else state.project().relative(artifact_path)
    )

    analysis_path = provenance.write_analysis(
        target_dir / f"{slug}.pubmed-bq.analysis.json",
        source=source_ref,
        threshold_set="pubmed-bq-search",
        thresholds_applied={},
        metrics=metrics,
        assessment=assessment,
        mandatory_relays=relays,
        suppress_warnings=as_json,
    )

    emit.data("assessment", assessment)
    emit.data("relays", relays)
    emit.line(f"PubMed SQL warehouse search analysis: {query!r}")
    emit.line(f"  Outcome: {outcome}")
    emit.line(f"  {len(results)} results retrieved")
    if year_distribution:
        emit.line(f"  Year range: {min(year_counts)}-{max(year_counts)}")
    if top_journals:
        emit.line("  Top journals:")
        for j, c in top_journals[:5]:
            emit.line(f"    {j}: {c}")
    if top_keywords:
        emit.line("  Top abstract keywords:")
        for t, c in top_keywords[:5]:
            emit.line(f"    {t}: {c}")
    for record in relays:
        emit.line(f"relay {record['code']}: {record['message']}")
    emit.path(analysis_path, role="analysis")
    emit.flush()
