# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""`pde custom` -- Bring-Your-Own-Algorithm (BYOA) & private data framework.

Two-phase command surface for local private data and proprietary algorithms:

  Phase 1A (`pde custom ingest`):
    Ingests local private datasets (.csv, .tsv, .json) into a Layer 0
    `raw/<class>/<slug>.custom.json` artifact with a SHA-256 provenance
    sidecar (`.custom.meta.json`).

  Phase 1B (`pde custom run`):
    Executes a user-supplied algorithm (Python script, compiled binary, or
    container command) against a local input file, captures its structured
    JSON output into `raw/<class>/<slug>.custom.json`, hashes both the input
    data and the algorithm script/binary into `.custom.meta.json`, and
    attaches `custom.external_algorithm_caveat`.

  Phase 2 (`pde custom analyze`):
    Runs strictly offline (`enforce_phase_two`), reads a Phase 1
    `.custom.json` artifact, evaluates a target numeric metric across
    records against the `custom-evaluation@1.0` threshold set (or program
    overrides in `.pde/thresholds.yaml`), and writes `.custom.analysis.json`
    with mandatory relays.
"""

from __future__ import annotations

import csv
import json
import re
import shlex
import statistics
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import click

from ..common import (
    AppState,
    PDEGroup,
    emitter,
    out_option,
    output_options,
    pass_state,
    resolve_artifact,
)
from ..core import provenance, thresholds
from ..core.context import ARTIFACT_DIRS, normalize_artifact_class
from ..core.errors import ArtifactError, PDEError, SchemaError, UsageError
from ..core.paths import is_safe_to_open

ARTIFACT_CLASS = "mpo"


def _slugify(text: str) -> str:
    """Normalize text to a safe lowercase filename slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not slug:
        raise UsageError(
            f"could not derive a valid filename slug from {text!r}",
            remedy="pass an alphanumeric --name (e.g., --name cns-lead-series)",
        )
    return slug


def _validate_artifact_class(artifact_class: str) -> str:
    """Validate and normalize an artifact class against ARTIFACT_DIRS."""
    normalized = normalize_artifact_class(artifact_class)
    if normalized not in ARTIFACT_DIRS:
        raise SchemaError(
            f"unknown artifact class: {artifact_class!r}",
            detail=f"known classes: {', '.join(sorted(ARTIFACT_DIRS))}",
            remedy="choose a valid class from `pde artifact classes`",
        )
    return normalized


def _coerce_cell(value: str) -> Any:
    """Convert CSV/TSV string cells to int, float, bool, or str."""
    text = value.strip()
    if text == "":
        return None
    low = text.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        return int(text)
    except ValueError:
        pass
    try:
        num = float(text)
        if num == num and num not in (float("inf"), float("-inf")):
            return num
    except ValueError:
        pass
    return text


def _load_structured_input(path: Path, id_col: str | None = None) -> dict[str, Any]:
    """Read a CSV, TSV, or JSON file and normalize into a structured dict."""
    if not path.is_file():
        raise ArtifactError(
            f"input file not found: {path}",
            remedy="provide a valid path to a .json, .csv, or .tsv file",
        )
    if not is_safe_to_open(path):
        raise ArtifactError(
            f"refusing to read input file through symlink: {path}",
            detail="symlink exploitation guard",
        )

    suffix = path.suffix.lower()
    if suffix in (".csv", ".tsv"):
        delimiter = "\t" if suffix == ".tsv" else ","
        raw_text = path.read_text(encoding="utf-8")
        reader = csv.DictReader(raw_text.splitlines(), delimiter=delimiter)
        if not reader.fieldnames:
            raise ArtifactError(
                f"tabular file has no header row: {path}",
                remedy="include column names on the first line of the file",
            )
        columns = [c.strip() for c in reader.fieldnames if c]
        records: list[dict[str, Any]] = []
        for idx, row in enumerate(reader, start=1):
            clean_row: dict[str, Any] = {}
            for k, v in row.items():
                if k is None:
                    continue
                clean_row[k.strip()] = _coerce_cell(v or "")
            if id_col and id_col in clean_row and clean_row[id_col] is not None:
                clean_row.setdefault("id", str(clean_row[id_col]))
            else:
                # Auto-detect common identifier columns
                for candidate in ("id", "compound_id", "compound", "name", "sample_id", "gene"):
                    if candidate in clean_row and clean_row[candidate] is not None:
                        clean_row.setdefault("id", str(clean_row[candidate]))
                        break
                else:
                    clean_row.setdefault("id", f"record-{idx}")
            records.append(clean_row)
        return {
            "format": suffix.lstrip("."),
            "columns": columns,
            "n_records": len(records),
            "records": records,
        }

    # Default: parse as JSON
    data = provenance.read_json(path, "input file")
    if isinstance(data, list):
        return {
            "format": "json",
            "n_records": len(data),
            "records": data,
        }
    if isinstance(data, dict):
        if "records" in data and isinstance(data["records"], list):
            return {
                "format": "json",
                "n_records": len(data["records"]),
                **data,
            }
        for list_key in ("compounds", "items", "results", "candidates", "rows"):
            if list_key in data and isinstance(data[list_key], list):
                return {
                    "format": "json",
                    "n_records": len(data[list_key]),
                    "records": data[list_key],
                    **data,
                }
        return {
            "format": "json",
            "n_records": 1,
            "records": [data],
            "payload": data,
        }
    raise ArtifactError(
        f"unsupported JSON top-level type in {path}: {type(data).__name__}",
        remedy="input JSON must be an object or array of objects",
    )


def _detect_algorithm_file(tokens: list[str], cwd: Path) -> Path | None:
    """Find a local script or executable path referenced in the command tokens."""
    if not tokens:
        return None
    interp_names = {
        "python",
        "python3",
        "bash",
        "sh",
        "Rscript",
        "julia",
        "node",
        "perl",
    }
    first_base = Path(tokens[0]).name
    candidates: list[str] = []
    if first_base in interp_names or first_base.startswith("python3."):
        for tok in tokens[1:]:
            if not tok.startswith("-"):
                candidates.append(tok)
                break
    else:
        candidates.append(tokens[0])

    for cand in candidates:
        p = Path(cand)
        resolved = p if p.is_absolute() else (cwd / p)
        if resolved.is_file():
            return resolved.resolve()
    return None


def _extract_records(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the list of record dicts from a Phase 1 .custom.json artifact."""
    for key in ("records", "compounds", "items", "results", "candidates", "rows"):
        val = doc.get(key)
        if isinstance(val, list) and all(isinstance(r, dict) for r in val):
            return val
    payload = doc.get("payload")
    if isinstance(payload, dict):
        for key in ("records", "compounds", "items", "results", "candidates", "rows"):
            val = payload.get(key)
            if isinstance(val, list) and all(isinstance(r, dict) for r in val):
                return val
        return [payload]
    return [doc]


def _resolve_record_id(
    record: dict[str, Any], index: int, id_field: str | None
) -> str:
    """Resolve a human-readable identifier for a record."""
    if id_field and id_field in record and record[id_field] is not None:
        return str(record[id_field])
    for candidate in (
        "id",
        "compound_id",
        "compound",
        "name",
        "sample_id",
        "gene",
        "target",
    ):
        if candidate in record and record[candidate] is not None:
            return str(record[candidate])
    return f"record-{index}"


def _resolve_metric_value(record: dict[str, Any], metric: str) -> float | None:
    """Look up a numeric metric value by key or dotted path."""
    curr: Any = record
    for part in metric.split("."):
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        else:
            curr = None
            break
    if curr is None and "metrics" in record and isinstance(record["metrics"], dict):
        curr = record["metrics"].get(metric)
    if curr is None and "scores" in record and isinstance(record["scores"], dict):
        curr = record["scores"].get(metric)
    if isinstance(curr, (int, float)) and not isinstance(curr, bool):
        return float(curr)
    return None


@click.group(cls=PDEGroup)
def custom() -> None:
    """Ingest private data and run proprietary (BYOA) algorithms."""


@custom.command("ingest")
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--class",
    "artifact_class",
    required=True,
    help="Target PDE artifact class (e.g., bioactivity, admet, mpo, pk, tox, descriptors).",
)
@click.option(
    "--name",
    "slug_name",
    required=True,
    help="Short identifier slug for the output artifact (e.g., internal-series-a).",
)
@click.option(
    "--id-col",
    default=None,
    help="Column or field name to use as the record identifier.",
)
@out_option
@output_options
@pass_state
def ingest(
    state: AppState,
    input_file: Path,
    artifact_class: str,
    slug_name: str,
    id_col: str | None,
    out: str | None,
    as_json: bool,
    quiet: bool,
) -> None:
    """Phase 1A: Ingest a private dataset (.csv, .tsv, .json) into Layer 0.

    Normalizes local tabular or JSON records into `raw/<class>/<name>.custom.json`
    and writes a matching `.custom.meta.json` provenance sidecar recording the
    SHA-256 digest of the source file.
    """
    emit = emitter(as_json, quiet)
    project = state.project()
    norm_class = _validate_artifact_class(artifact_class)
    slug = _slugify(slug_name)

    input_resolved = input_file.expanduser().resolve()
    input_digest = provenance.sha256_file(input_resolved)
    normalized = _load_structured_input(input_resolved, id_col=id_col)

    target_dir = project.artifact_dir(norm_class, out)
    artifact_path = target_dir / f"{slug}.custom.json"
    meta_path = target_dir / f"{slug}.custom.meta.json"

    record: dict[str, Any] = {
        "schema": "pde.custom-dataset.v1",
        "tool": "custom",
        "subcommand": "ingest",
        "artifact_class": norm_class,
        "dataset_name": slug,
        "source_filename": input_resolved.name,
        "source_sha256": input_digest,
        "source_format": normalized.get("format", "json"),
        "n_records": normalized.get("n_records", 0),
    }
    if "columns" in normalized:
        record["columns"] = normalized["columns"]
    record["records"] = normalized.get("records", [])

    artifact_path.write_text(
        json.dumps(record, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    sidecar = provenance.Sidecar(
        tool="custom",
        subcommand="ingest",
        endpoint="local:private-data",
        parameters={
            "artifact_class": norm_class,
            "name": slug,
            "source_filename": input_resolved.name,
            "source_sha256": input_digest,
            "id_col": id_col,
        },
    )
    sidecar.note("n_records", record["n_records"])
    sidecar.add_output(artifact_path)
    sidecar.write(meta_path)

    emit.line(
        f"Ingested {record['n_records']} record(s) from {input_resolved.name} "
        f"-> {project.relative(artifact_path)}"
    )
    emit.data("dataset_name", slug)
    emit.data("artifact_class", norm_class)
    emit.data("n_records", record["n_records"])
    emit.data("source_sha256", input_digest)
    emit.path(artifact_path, role="artifact")
    emit.path(meta_path, role="sidecar")
    emit.flush()


@custom.command("run")
@click.option(
    "--cmd",
    "cmd_template",
    required=True,
    help=(
        "Command to execute. May include {input} and {output} placeholders "
        "(e.g. 'python3 examples/byoa/proprietary_cns_mpo_scorer.py --input {input} --output {output}'). "
        "If placeholders are omitted, '--input <path> --output <path>' is appended."
    ),
)
@click.option(
    "--input",
    "input_file",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Input dataset file (.json, .csv, .tsv) passed to the algorithm.",
)
@click.option(
    "--class",
    "artifact_class",
    required=True,
    help="Target PDE artifact class (e.g., mpo, admet, bioactivity, pk, tox, docking).",
)
@click.option(
    "--name",
    "slug_name",
    required=True,
    help="Short identifier slug for the output artifact.",
)
@click.option(
    "--algorithm-id",
    default=None,
    help="Optional identifier/version tag for the proprietary algorithm (e.g., cns-bbb-mpo@2.1).",
)
@click.option(
    "--timeout",
    default=300,
    type=int,
    show_default=True,
    help="Maximum execution time in seconds.",
)
@out_option
@output_options
@pass_state
def run_cmd(
    state: AppState,
    cmd_template: str,
    input_file: Path,
    artifact_class: str,
    slug_name: str,
    algorithm_id: str | None,
    timeout: int,
    out: str | None,
    as_json: bool,
    quiet: bool,
) -> None:
    """Phase 1B: Run a proprietary algorithm and capture its Layer 0 output.

    Executes the user-supplied command locally, captures its JSON output into
    `raw/<class>/<name>.custom.json`, records SHA-256 digests of both the input
    dataset and the algorithm script/executable in `.custom.meta.json`, and
    attaches the mandatory relay `custom.external_algorithm_caveat`.
    """
    emit = emitter(as_json, quiet)
    project = state.project()
    norm_class = _validate_artifact_class(artifact_class)
    slug = _slugify(slug_name)

    input_resolved = input_file.expanduser().resolve()
    if not is_safe_to_open(input_resolved):
        raise ArtifactError(
            f"refusing to read input file through symlink: {input_resolved}",
            detail="symlink exploitation guard",
        )
    input_digest = provenance.sha256_file(input_resolved)

    target_dir = project.artifact_dir(norm_class, out)
    artifact_path = target_dir / f"{slug}.custom.json"
    meta_path = target_dir / f"{slug}.custom.meta.json"

    with tempfile.NamedTemporaryFile(
        prefix="pde-custom-out-", suffix=".json", delete=False
    ) as tmp_out:
        tmp_output_path = Path(tmp_out.name)

    try:
        has_input_ph = "{input}" in cmd_template
        has_output_ph = "{output}" in cmd_template
        if has_input_ph or has_output_ph:
            formatted = cmd_template.replace(
                "{input}", shlex.quote(str(input_resolved))
            ).replace("{output}", shlex.quote(str(tmp_output_path)))
            argv = shlex.split(formatted)
        else:
            argv = [
                *shlex.split(cmd_template),
                "--input",
                str(input_resolved),
                "--output",
                str(tmp_output_path),
            ]

        if not argv:
            raise UsageError("empty --cmd provided")

        algo_file = _detect_algorithm_file(argv, Path.cwd())
        algo_sha256 = provenance.sha256_file(algo_file) if algo_file else None
        algo_label = algorithm_id or (algo_file.name if algo_file else argv[0])

        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise PDEError(
                f"custom algorithm timed out after {timeout}s: {algo_label}",
                remedy="increase --timeout or optimize the algorithm execution",
            ) from exc
        except OSError as exc:
            raise PDEError(
                f"failed to launch custom algorithm {algo_label!r}",
                detail=str(exc),
                remedy="verify the command path and executable permissions",
            ) from exc

        if proc.returncode != 0:
            stderr_snippet = (proc.stderr or proc.stdout or "").strip()[:600]
            raise PDEError(
                f"custom algorithm exited with code {proc.returncode}: {algo_label}",
                detail=stderr_snippet or "no stderr output",
                remedy="inspect the algorithm script/binary error message above",
            )

        # Read output from tmp_output_path if non-empty, else fallback to stdout
        raw_output_text = ""
        if tmp_output_path.is_file() and tmp_output_path.stat().st_size > 0:
            raw_output_text = tmp_output_path.read_text(encoding="utf-8").strip()
        if not raw_output_text and proc.stdout:
            raw_output_text = proc.stdout.strip()

        if not raw_output_text:
            raise ArtifactError(
                f"custom algorithm {algo_label!r} produced no JSON output",
                remedy="ensure the algorithm writes JSON to --output or stdout",
            )

        try:
            parsed_out = json.loads(raw_output_text)
        except json.JSONDecodeError as exc:
            raise ArtifactError(
                f"custom algorithm {algo_label!r} output is not valid JSON",
                detail=str(exc),
                remedy="ensure the algorithm writes valid JSON to --output or stdout",
            ) from exc
    finally:
        tmp_output_path.unlink(missing_ok=True)

    if isinstance(parsed_out, list):
        records = parsed_out
        extra_payload: dict[str, Any] = {}
    elif isinstance(parsed_out, dict):
        records = _extract_records(parsed_out)
        extra_payload = {
            k: v
            for k, v in parsed_out.items()
            if k not in ("schema", "tool", "subcommand", "records")
        }
    else:
        raise ArtifactError(
            f"custom algorithm output must be a JSON object or array, got {type(parsed_out).__name__}"
        )

    relays = [
        provenance.relay(
            "custom.external_algorithm_caveat",
            provenance.RELAY_CODES["custom.external_algorithm_caveat"],
        )
    ]

    record: dict[str, Any] = {
        "schema": "pde.custom-algorithm-output.v1",
        "tool": "custom",
        "subcommand": "run",
        "artifact_class": norm_class,
        "dataset_name": slug,
        "algorithm_id": algo_label,
        "algorithm_sha256": algo_sha256,
        "source_filename": input_resolved.name,
        "source_sha256": input_digest,
        "n_records": len(records),
        **extra_payload,
        "records": records,
        "mandatory_relays": relays,
    }

    artifact_path.write_text(
        json.dumps(record, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    sidecar = provenance.Sidecar(
        tool="custom",
        subcommand="run",
        endpoint=f"local:byoa:{algo_label}",
        parameters={
            "artifact_class": norm_class,
            "name": slug,
            "algorithm_id": algo_label,
            "algorithm_sha256": algo_sha256,
            "source_filename": input_resolved.name,
            "source_sha256": input_digest,
        },
    )
    sidecar.note("n_records", len(records))
    for r in relays:
        sidecar.warn(r["message"], code=r["code"])
    sidecar.add_output(artifact_path)
    sidecar.write(meta_path)

    emit.line(
        f"Executed {algo_label} on {input_resolved.name} ({len(records)} record(s)) "
        f"-> {project.relative(artifact_path)}"
    )
    for r in relays:
        emit.line(f"relay {r['code']}: {r['message']}")
    emit.data("dataset_name", slug)
    emit.data("algorithm_id", algo_label)
    emit.data("algorithm_sha256", algo_sha256)
    emit.data("n_records", len(records))
    emit.data("mandatory_relays", relays)
    emit.path(artifact_path, role="artifact")
    emit.path(meta_path, role="sidecar")
    emit.flush()


@custom.command("analyze")
@click.argument("artifact_path", type=click.Path(dir_okay=False, path_type=Path))
@click.option(
    "--metric",
    required=True,
    help="Numeric field or dotted key to evaluate across records (e.g., cns_bbb_score).",
)
@click.option(
    "--id-field",
    default=None,
    help="Field name used to identify each record in the assessment.",
)
@click.option(
    "--pass-cutoff",
    default=None,
    type=float,
    help="Override pass cutoff from custom-evaluation@1.0.",
)
@click.option(
    "--warn-cutoff",
    default=None,
    type=float,
    help="Override warning cutoff from custom-evaluation@1.0.",
)
@click.option(
    "--direction",
    type=click.Choice(["higher", "lower"]),
    default=None,
    help="Whether higher or lower values of --metric are better.",
)
@click.option(
    "--calibrated",
    is_flag=True,
    default=False,
    help="Declare that the applied cutoffs are calibrated against a cited reference standard.",
)
@out_option
@output_options
@pass_state
def analyze(
    state: AppState,
    artifact_path: Path,
    metric: str,
    id_field: str | None,
    pass_cutoff: float | None,
    warn_cutoff: float | None,
    direction: str | None,
    calibrated: bool,
    out: str | None,
    as_json: bool,
    quiet: bool,
) -> None:
    """Phase 2: Offline thresholded evaluation of a `.custom.json` artifact.

    Reads a Phase 1 artifact produced by `pde custom ingest` or `pde custom run`,
    extracts `--metric` across records, classifies each record (`PASS`, `WARN`,
    `FAIL`) using the `custom-evaluation@1.0` threshold set, and writes a
    `.custom.analysis.json` record with mandatory relays.
    """
    emit = emitter(as_json, quiet)
    project = state.project()

    # Resolve path inside project or directly if existing
    if artifact_path.is_file():
        resolved_input = artifact_path.resolve()
    else:
        candidate = project.root / artifact_path
        if candidate.is_file():
            resolved_input = candidate.resolve()
        else:
            resolved_input = resolve_artifact(project, ARTIFACT_CLASS, artifact_path)

    doc = provenance.read_json(resolved_input, "custom artifact")
    if not isinstance(doc, dict):
        raise ArtifactError(
            f"expected JSON object in {resolved_input}, got {type(doc).__name__}"
        )

    overrides: dict[str, Any] = {}
    if pass_cutoff is not None:
        overrides["pass_cutoff"] = pass_cutoff
    if warn_cutoff is not None:
        overrides["warn_cutoff"] = warn_cutoff
    if direction is not None:
        overrides["higher_is_better"] = direction == "higher"

    tset = thresholds.load("custom-evaluation", project.root, overrides=overrides)
    pass_val = float(tset.get("pass_cutoff"))
    warn_val = float(tset.get("warn_cutoff"))
    higher_is_better = bool(tset.get("higher_is_better"))

    if higher_is_better and pass_val < warn_val:
        raise UsageError(
            f"--pass-cutoff ({pass_val}) must be >= --warn-cutoff ({warn_val}) when direction is 'higher'"
        )
    if not higher_is_better and pass_val > warn_val:
        raise UsageError(
            f"--pass-cutoff ({pass_val}) must be <= --warn-cutoff ({warn_val}) when direction is 'lower'"
        )

    records = _extract_records(doc)
    evaluated: list[dict[str, Any]] = []
    numeric_values: list[float] = []
    pass_ids: list[str] = []
    warn_ids: list[str] = []
    fail_ids: list[str] = []
    missing_ids: list[str] = []

    for idx, rec in enumerate(records, start=1):
        rec_id = _resolve_record_id(rec, idx, id_field)
        val = _resolve_metric_value(rec, metric)
        if val is None:
            missing_ids.append(rec_id)
            evaluated.append(
                {
                    "id": rec_id,
                    "metric": metric,
                    "value": None,
                    "classification": "MISSING",
                }
            )
            continue

        numeric_values.append(val)
        if higher_is_better:
            if val >= pass_val:
                cls_label = "PASS"
                pass_ids.append(rec_id)
            elif val >= warn_val:
                cls_label = "WARN"
                warn_ids.append(rec_id)
            else:
                cls_label = "FAIL"
                fail_ids.append(rec_id)
        else:
            if val <= pass_val:
                cls_label = "PASS"
                pass_ids.append(rec_id)
            elif val <= warn_val:
                cls_label = "WARN"
                warn_ids.append(rec_id)
            else:
                cls_label = "FAIL"
                fail_ids.append(rec_id)

        evaluated.append(
            {
                "id": rec_id,
                "metric": metric,
                "value": round(val, 6),
                "classification": cls_label,
            }
        )

    if not numeric_values:
        raise ArtifactError(
            f"metric {metric!r} was not found with numeric values in any record of {resolved_input.name}",
            remedy="check the field name in the Phase 1 .custom.json artifact and pass --metric <field>",
        )

    # Sort ranked records (best first)
    ranked_eval = sorted(
        [e for e in evaluated if e["value"] is not None],
        key=lambda x: x["value"],
        reverse=higher_is_better,
    )
    top_record = ranked_eval[0] if ranked_eval else None

    metrics_block: dict[str, Any] = {
        "metric_name": metric,
        "direction": "higher_is_better" if higher_is_better else "lower_is_better",
        "n_total_records": len(records),
        "n_evaluated": len(numeric_values),
        "n_missing": len(missing_ids),
        "min": round(min(numeric_values), 6),
        "max": round(max(numeric_values), 6),
        "mean": round(statistics.mean(numeric_values), 6),
        "median": round(statistics.median(numeric_values), 6),
        "pass_count": len(pass_ids),
        "warn_count": len(warn_ids),
        "fail_count": len(fail_ids),
    }
    if doc.get("algorithm_id"):
        metrics_block["algorithm_id"] = doc["algorithm_id"]
    if doc.get("algorithm_sha256"):
        metrics_block["algorithm_sha256"] = doc["algorithm_sha256"]

    if len(pass_ids) > 0 and len(fail_ids) == 0:
        overall_verdict = "FAVORABLE"
    elif len(pass_ids) > 0:
        overall_verdict = "MIXED"
    else:
        overall_verdict = "UNFAVORABLE"

    assessment_block: dict[str, Any] = {
        "overall_verdict": overall_verdict,
        "top_candidate": top_record["id"] if top_record else None,
        "top_value": top_record["value"] if top_record else None,
        "pass_ids": pass_ids,
        "warn_ids": warn_ids,
        "fail_ids": fail_ids,
        "records": evaluated,
    }

    relays: list[dict[str, str]] = []
    if doc.get("subcommand") == "run" or doc.get("algorithm_id"):
        relays.append(
            provenance.relay(
                "custom.external_algorithm_caveat",
                provenance.RELAY_CODES["custom.external_algorithm_caveat"],
            )
        )

    sources_map = tset.sources()
    has_program_calibration = any(v == "program" for v in sources_map.values())
    if not calibrated and not has_program_calibration:
        relays.append(
            provenance.relay(
                "custom.uncalibrated_threshold",
                provenance.RELAY_CODES["custom.uncalibrated_threshold"],
            )
        )

    if fail_ids:
        relays.append(
            provenance.relay(
                "custom.liability_flagged",
                provenance.RELAY_CODES["custom.liability_flagged"],
            )
        )

    # Determine output directory and analysis filename
    if out is not None:
        out_dir = project.artifact_dir(
            doc.get("artifact_class", ARTIFACT_CLASS), out
        )
    else:
        out_dir = resolved_input.parent

    base_name = resolved_input.name
    if base_name.endswith(".json"):
        stem = base_name[:-5]
    else:
        stem = resolved_input.stem
    analysis_path = out_dir / f"{stem}.analysis.json"

    provenance.write_analysis(
        path=analysis_path,
        source=resolved_input,
        threshold_set=tset.tag,
        thresholds_applied=tset.applied(),
        metrics=metrics_block,
        assessment=assessment_block,
        threshold_sources=tset.sources(),
        threshold_provenance=tset.provenance,
        unresolved=tset.unresolved(),
        mandatory_relays=relays,
    )

    emit.line(
        f"Analyzed {resolved_input.name} on metric {metric!r} ({tset.tag}): "
        f"PASS={len(pass_ids)}, WARN={len(warn_ids)}, FAIL={len(fail_ids)} "
        f"-> {project.relative(analysis_path)}"
    )
    for r in relays:
        emit.line(f"relay {r['code']}: {r['message']}")
    emit.data("metrics", metrics_block)
    emit.data("assessment", assessment_block)
    if relays:
        emit.data("mandatory_relays", relays)
    emit.path(analysis_path, role="analysis")
    emit.flush()
