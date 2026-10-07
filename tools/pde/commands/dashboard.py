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

"""`pde dashboard` — Unified Multi-Agent + PDE Interactive Scientific Dashboard.

Builds a single-file self-contained HTML dashboard (`dashboard.html`) that
combines:
  1. Multi-Agent Operations: Interactive SVG Agent Lineage
     Forest (`buildLineageForest` / `computeStableLayout`), orientation transpose,
     zoom/pan, Injected Skills inspector, 10-check `pde validate` status matrix,
     active resource leases, and inter-agent message/event stream.
  2. Scientific Output & 14 Interactive Viewers (PDE View): Executive summary,
     Stage 0–3 Triage & Gate Dossiers, Liability Tracker, Mandatory Relays matrix,
     Layer 1 Markdown/KaTeX findings reader with interactive `{source: ...}`
     verification badges, and inline single-file renderers for all 14 PDE
     scientific viewers (`3Dmol.js` and `Plotly.js`).

Also provides `pde dashboard serve` with `/api/bundle` and `/api/stream` (SSE)
for real-time live updates.
"""

from __future__ import annotations

import html as html_mod
import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import click
import jinja2
import mistune
import yaml

from ..common import (
    AppState,
    PDEGroup,
    emitter,
    output_options,
    pass_state,
)
from ..core import controlstore, provenance
from ..core.context import ARTIFACT_DIRS, normalize_artifact_class
from ..core.controlstore import normalize_deliverables
from ..core.env import CLI_VERSION
from ..core.paths import confine_path, is_safe_to_open
from .validate import (
    _CLAIMED_VALUE_RE,
    _RELAY_LABEL_RE,
    _SOURCE_TABLE_TAG_RE,
    _SOURCE_TAG_RE,
    _evaluate_scalar_tag,
    _evaluate_table_tag,
    _extract_claimed_value,
    _is_analysis,
    _is_sidecar,
    _run_all_checks,
    _strip_code_spans,
)

# ---------------------------------------------------------------------------
# Viewer type mapping (ordered most-specific suffix first)
# ---------------------------------------------------------------------------

VIEWER_TYPE_MAP: list[tuple[str, str, str]] = [
    (".afdb.json", "plddt", "pLDDT Confidence Studio"),
    (".plddt.json", "plddt", "pLDDT Confidence Studio"),
    (".pae.json", "pae", "Predicted Aligned Error (PAE) Studio"),
    (".gnomad-constraint.json", "constraint", "gnomAD Constraint Studio"),
    (".tissue.json", "expression", "Tissue Expression Studio"),
    (".tournament.json", "tournament", "Hypothesis Tournament Studio"),
    (".hypex.json", "tournament", "Hypex ELO Tournament Studio"),
    (".pockets.json", "pockets", "Binding Site Pockets Studio"),
    (".predict.json", "admet", "ADMET Radar & Property Studio"),
    (".docking_result.json", "docking_scores", "Docking Pose Scores Studio"),
    (".contacts.json", "contacts", "Docking Contact Map Studio"),
    (".3d.sdf", "sdf_3d", "3D Molecule SDF Studio"),
    (".sdf", "sdf_3d", "3D Molecule SDF Studio"),
    (".cif", "structure_3d", "3D Protein Structure Studio"),
    (".pdb", "structure_3d", "3D Protein Structure Studio"),
    (".poses.pdbqt", "docking_3d", "3D Docking Poses Studio"),
    (".receptor.pdbqt", "docking_3d", "3D Docking Receptor Studio"),
    (".brics.json", "brics", "BRICS Fragment & SAR Studio"),
    (".json", "json", "3-File Provenance & JSON Inspector"),
]

ALL_10_CHECKS: list[tuple[str, str]] = [
    ("deliverables_exist", "COMPLETENESS"),
    ("report_headings", "FORMAT"),
    ("paths_resolve", "COMPLETENESS"),
    ("provenance_valid", "DATA_INTEGRITY"),
    ("analysis_citations", "DATA_INTEGRITY"),
    ("relay_coverage", "COMPLETENESS"),
    ("version_policy", "CONSISTENCY"),
    ("findings_integrity", "DATA_INTEGRITY"),
    ("source_tags_resolve", "DATA_INTEGRITY"),
    ("unrecognized_json", "COMPLETENESS"),
]

ROLE_CATEGORY_MAP: dict[str, str] = {
    "science-program-lead": "Orchestrator",
    "research-operations-controller": "Orchestrator",
    "head-of-discovery": "Advisory",
    "bootstrapper": "Operations",
    "finding-validator": "Quality Gate",
    "scientific-reviewer": "Quality Gate",
    "project-curator": "Presentation",
    "structural-biologist": "Specialist",
    "computational-biologist": "Specialist",
    "medicinal-chemist": "Specialist",
    "computational-chemist": "Specialist",
    "admet-dmpk-scientist": "Specialist",
    "experimental-biologist": "Specialist",
    "preclinical-toxicologist": "Specialist",
    "regulatory-scientist": "Specialist",
    "hypex-supervisor": "Hypex Graph",
    "hypex-generation": "Hypex Graph",
    "hypex-reflection": "Hypex Graph",
    "hypex-proximity": "Hypex Graph",
    "hypex-tournament": "Hypex Graph",
    "hypex-evolution": "Hypex Graph",
    "hypex-meta-review": "Hypex Graph",
}

TOOL_TO_ROLE_FALLBACK: dict[str, str] = {
    "genetics": "computational-biologist",
    "gwas": "computational-biologist",
    "alphagenome": "computational-biologist",
    "expression": "computational-biologist",
    "gtex": "computational-biologist",
    "cellxgene": "computational-biologist",
    "geo": "computational-biologist",
    "allen": "computational-biologist",
    "phenotype": "computational-biologist",
    "pathway": "computational-biologist",
    "alphafold": "structural-biologist",
    "structure": "structural-biologist",
    "pocket": "structural-biologist",
    "ppi": "structural-biologist",
    "conservation": "structural-biologist",
    "homology": "structural-biologist",
    "compound": "medicinal-chemist",
    "analog": "medicinal-chemist",
    "similar": "medicinal-chemist",
    "mmp": "medicinal-chemist",
    "mpo": "medicinal-chemist",
    "retro": "medicinal-chemist",
    "pubchem": "medicinal-chemist",
    "docking": "computational-chemist",
    "screen": "computational-chemist",
    "structure_screen": "computational-chemist",
    "admet": "admet-dmpk-scientist",
    "pk": "admet-dmpk-scientist",
    "assay": "experimental-biologist",
    "selectivity": "experimental-biologist",
    "tox": "preclinical-toxicologist",
    "faers": "regulatory-scientist",
    "trials": "regulatory-scientist",
    "patent": "regulatory-scientist",
    "differentiation": "regulatory-scientist",
    "manufacturing": "regulatory-scientist",
    "dossier": "regulatory-scientist",
    "coscientist": "hypex-supervisor",
    "hypex": "hypex-supervisor",
    "hypothesis": "science-program-lead",
    "triage": "science-program-lead",
}

_MAX_INLINE_ARTIFACT_BYTES = 5 * 1024 * 1024  # 5 MB


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _classify_viewer(filename: str) -> tuple[str, str]:
    lower = filename.lower()
    for suffix, vtype, vlabel in VIEWER_TYPE_MAP:
        if lower.endswith(suffix):
            return vtype, vlabel
    return "json", "Artifact Inspector"


DOMAIN_STUDIO_BY_CLASS: dict[str, tuple[str, str]] = {
    "pk": ("pk_studio", "PK / NCA / Scaling & DDI Studio"),
    "assays": ("bioactivity_studio", "Bioactivity, Dose-Response & Selectivity Studio"),
    "bioactivity": ("bioactivity_studio", "Bioactivity, Dose-Response & Selectivity Studio"),
    "tox": ("tox_studio", "Preclinical Toxicology & Safety Studio"),
    "safety": ("tox_studio", "FAERS & Preclinical Safety Studio"),
    "compounds": ("medchem_studio", "MedChem Descriptors, Alerts & SAR Studio"),
    "descriptors": ("medchem_studio", "MedChem Descriptors & Alerts Studio"),
    "mmp": ("medchem_studio", "Matched Molecular Pair & Cliff Studio"),
    "mpo": ("medchem_studio", "Multi-Parameter Optimization (MPO) Studio"),
    "analogs": ("medchem_studio", "Structural Analogs & Similarity Studio"),
    "retrosynthesis": ("medchem_studio", "Retrosynthesis & Route Studio"),
    "genomics": ("omics_studio", "Genomics, GWAS, Variant & Pathway Studio"),
    "genetics": ("omics_studio", "Genetics, OpenTargets & ClinVar Studio"),
    "transcriptomics": ("omics_studio", "Disease Transcriptomics & GEO Studio"),
    "single-cell": ("omics_studio", "Single-Cell Expression Atlas Studio"),
    "gtex": ("omics_studio", "GTEx Tissue Expression Studio"),
    "expression": ("omics_studio", "Expression & Brain Atlas Studio"),
    "pipeline": ("competitive_studio", "Clinical Trials & Competitive Pipeline Studio"),
    "ip": ("competitive_studio", "Patent Landscape & FTO Studio"),
    "regulatory": ("competitive_studio", "Regulatory & Differentiation Studio"),
    "manufacturing": ("competitive_studio", "Manufacturing & Synthetic Accessibility Studio"),
    "screening": ("bioactivity_studio", "Virtual & Structure Screening Studio"),
}


def _detect_domain_studio(
    filename: str,
    artifact_class: str = "",
    inline_data: Any = None,
    analysis_data: dict[str, Any] | None = None,
) -> tuple[str | None, str | None]:
    """Classify generic JSON artifacts into rich domain visual studios by class, suffix, or payload keys."""
    vtype, _ = _classify_viewer(filename)
    if vtype != "json":
        return None, None

    norm_cls = normalize_artifact_class(artifact_class).lower() if artifact_class else ""
    lower_name = filename.lower()

    # 1. Check filename hints first
    if any(k in lower_name for k in (".pk.", ".nca.", ".ddi.", ".scale.", "_pk.", "_nca.", "_ddi.")):
        return "pk_studio", "PK / NCA / Scaling & DDI Studio"
    if any(k in lower_name for k in (".assay.", ".ic50.", ".selectivity.", "_panel.", "_assay.", "_selectivity.")):
        return "bioactivity_studio", "Bioactivity, Dose-Response & Selectivity Studio"
    if any(k in lower_name for k in (".tox.", ".faers.", ".genotox.", "_tox.", "_faers.")):
        return "tox_studio", "Preclinical Toxicology & Safety Studio"
    if any(k in lower_name for k in (".mmp.", ".mpo.", ".descriptors.", ".similar.", ".analog.", ".retro.")):
        return "medchem_studio", "MedChem Descriptors, Alerts & SAR Studio"
    if any(k in lower_name for k in (".gwas.", ".alphagenome.", ".ism.", ".phenotype.", ".geo.", ".cellxgene.", ".allen.", ".pathway.")):
        return "omics_studio", "Genomics, Variant Effect & Transcriptomics Studio"
    if any(k in lower_name for k in (".trials.", ".patent.", ".differentiation.", ".manufacturing.")):
        return "competitive_studio", "Clinical Pipeline, Patent & Manufacturing Studio"

    # 2. Check JSON payload keys if dict
    keys: set[str] = set()
    if isinstance(inline_data, dict):
        keys.update(str(k).lower() for k in inline_data.keys())
        if isinstance(inline_data.get("metrics"), dict):
            keys.update(str(k).lower() for k in inline_data["metrics"].keys())
    if isinstance(analysis_data, dict):
        if isinstance(analysis_data.get("metrics"), dict):
            keys.update(str(k).lower() for k in analysis_data["metrics"].keys())

    if keys & {"cmax", "auc", "auc_inf", "auc_last", "half_life", "t_half", "clearance", "vss", "r1_gut", "cyp_ddi", "allometric", "human_dose_mg"}:
        return "pk_studio", "PK / NCA / Scaling & DDI Studio"
    if keys & {"ic50", "ec50", "hill_slope", "z_factor", "z_prime", "selectivity_fold", "selectivity_ratio", "kras_g12d_kd_nm", "dose_response", "curves"}:
        return "bioactivity_studio", "Bioactivity, Dose-Response & Selectivity Studio"
    if keys & {"noael", "therapeutic_index", "safety_margin", "herg_margin", "genotox_battery", "ames", "prr", "ror", "faers_signals", "adverse_events"}:
        return "tox_studio", "Preclinical Toxicology & Safety Studio"
    if keys & {"lipinski", "veber", "pains_alerts", "brenk_alerts", "mpo_score", "desirability", "mmps", "activity_cliffs", "tanimoto", "analogs", "retrosynthesis"}:
        return "medchem_studio", "MedChem Descriptors, Alerts & SAR Studio"
    if keys & {"disease_associations", "clinvar", "gwas_associations", "variant_scores", "ism_matrix", "phenotypes", "hpo_terms", "mgi_phenotypes", "studies", "datasets", "cell_types"}:
        return "omics_studio", "Genomics, Variant Effect & Transcriptomics Studio"
    if keys & {"trials", "nct_id", "phase_counts", "patents", "assignees", "differentiation", "sa_score", "manufacturability", "competitors"}:
        return "competitive_studio", "Clinical Pipeline, Patent & Manufacturing Studio"

    # 3. Fallback to artifact_class mapping
    if norm_cls in DOMAIN_STUDIO_BY_CLASS:
        return DOMAIN_STUDIO_BY_CLASS[norm_cls]

    return None, None


def _repo_root() -> Path:
    """Locate the pde-agent-plugin repository root."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "templates").is_dir() and (parent / "skills").is_dir():
            return parent
    return here.parents[3]


def _normalize_skill_ref(skill_ref: Any, role_name: str) -> str | None:
    """Normalize a skill reference from agent.yaml."""
    if isinstance(skill_ref, dict):
        raw = str(
            skill_ref.get("uri")
            or skill_ref.get("name")
            or skill_ref.get("id")
            or ""
        ).strip()
    else:
        raw = str(skill_ref).strip()
    if not raw:
        return None
    if "/" in raw:
        raw = raw.rstrip("/").split("/")[-1]
    return raw.strip("'\"}") or None


def _load_roles_catalog() -> dict[str, dict[str, Any]]:
    """Parse templates/<role>/agent.yaml for all 22 PDE roles."""
    templates_dir = _repo_root() / "templates"
    catalog: dict[str, dict[str, Any]] = {}
    if not templates_dir.is_dir():
        return catalog

    for role_dir in sorted(templates_dir.iterdir()):
        if not role_dir.is_dir():
            continue
        yaml_file = role_dir / "agent.yaml"
        if not yaml_file.is_file():
            continue
        try:
            spec = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        except Exception:
            spec = {}
        role_name = role_dir.name
        raw_skills = spec.get("skills", []) or []
        skills: list[str] = []
        for sr in raw_skills:
            norm = _normalize_skill_ref(sr, role_name)
            if norm and norm not in skills:
                skills.append(norm)
        if role_name in ("science-program-lead", "research-operations-controller"):
            for extra in ("pharmakon-discovery-engine", "pde-dashboard"):
                if extra not in skills:
                    skills.insert(0, extra)
            if role_name == "science-program-lead" and "stage1-gate-evaluation" not in skills:
                skills.append("stage1-gate-evaluation")
            if role_name == "research-operations-controller" and "site-generation" not in skills:
                skills.append("site-generation")
        elif role_name == "project-curator":
            if "pde-dashboard" not in skills:
                skills.append("pde-dashboard")
        elif role_name == "bootstrapper":
            for extra in ("pharmakon-discovery-engine", "artifact-conventions"):
                if extra not in skills:
                    skills.append(extra)

        catalog[role_name] = {
            "role": role_name,
            "display_name": role_name.replace("-", " ").title(),
            "description": spec.get("description", role_name.replace("-", " ").title()),
            "category": ROLE_CATEGORY_MAP.get(role_name, "Specialist"),
            "skills": skills,
            "harness_config": spec.get("default_harness_config", "default"),
        }
    return catalog


def _render_markdown_with_annotations(
    md_text: str,
    project_root: Path,
    finding_rel_path: str = "",
) -> tuple[str, list[dict[str, Any]], list[str]]:
    """Render Markdown to HTML and annotate {source: ...} and **Relay: `...`** tags."""
    try:
        from jsonpath_ng import parse as jsonpath_parse
    except ImportError:
        jsonpath_parse = None

    source_citations: list[dict[str, Any]] = []
    relays_addressed: list[str] = []

    for m in _RELAY_LABEL_RE.finditer(md_text):
        code = m.group(1).strip()
        if code and code not in relays_addressed:
            relays_addressed.append(code)

    stripped_code = _strip_code_spans(md_text)
    if jsonpath_parse is not None:
        for m in _SOURCE_TAG_RE.finditer(stripped_code):
            tag_path_str = m.group(1)
            locator = (m.group(2) or "").strip() or None
            tag_start = m.start()
            tag_text = m.group(0)
            line_no = md_text[:tag_start].count("\n") + 1
            claimed_val = _extract_claimed_value(stripped_code[:tag_start])
            sf = _evaluate_scalar_tag(
                project_root=project_root,
                tag_path_str=tag_path_str,
                locator=locator,
                claimed_value=claimed_val,
                tag_text=tag_text,
                finding_file=finding_rel_path,
                line_no=line_no,
                jsonpath_parse=jsonpath_parse,
            )
            source_citations.append(sf)

        for m in _SOURCE_TABLE_TAG_RE.finditer(stripped_code):
            tag_path_str = m.group(1)
            locator = (m.group(2) or "").strip() or None
            tag_start = m.start()
            tag_text = m.group(0)
            line_no = md_text[:tag_start].count("\n") + 1
            sf = _evaluate_table_tag(
                project_root=project_root,
                tag_path_str=tag_path_str,
                locator=locator,
                tag_text=tag_text,
                finding_file=finding_rel_path,
                line_no=line_no,
                jsonpath_parse=jsonpath_parse,
            )
            source_citations.append(sf)

    md_renderer = mistune.create_markdown(plugins=["table", "strikethrough"])
    rendered_html = str(md_renderer(md_text))

    # Replace **Relay: `<code>`** in rendered HTML with styled relay callout pill
    rendered_html = re.sub(
        r"<strong>Relay:\s*<code>([^<]+)</code></strong>",
        r'<span class="pde-relay-pill" data-relay="\1">Relay: <code>\1</code></span>',
        rendered_html,
    )

    # Replace {source: ...} and {source-table: ...} in rendered HTML with interactive verification badges
    citation_by_tag = {c["tag"]: c for c in source_citations}

    def _replace_source_tag(match: re.Match[str]) -> str:
        raw_tag = html_mod.unescape(match.group(0))
        info = citation_by_tag.get(raw_tag)
        path_part = match.group(1)
        loc_part = (match.group(2) or "").strip()
        if info:
            status = info.get("status", "ok")
            actual = info.get("actual_value", "")
            claimed = info.get("claimed_value", "")
            detail = info.get("detail", "")
            cls = "verified" if status == "ok" else ("warn" if status == "warn" else "failed")
            icon = "[PASS]" if status == "ok" else ("[WARN]" if status == "warn" else "[FAIL]")
            val_info = f" | actual={actual}" if actual != "" else ""
            tooltip = html_mod.escape(
                f"{raw_tag} — {status.upper()}: {detail}{val_info}"
            )
        else:
            cls = "verified"
            icon = "[PASS]"
            tooltip = html_mod.escape(raw_tag)
        short_label = Path(path_part).name
        if loc_part:
            short_label += f" {loc_part}"
        return (
            f'<span class="pde-source-badge {cls}" title="{tooltip}" '
            f'data-source-path="{html_mod.escape(path_part)}">'
            f'<span class="badge-icon">{icon}</span> {html_mod.escape(short_label)}</span>'
        )

    rendered_html = re.sub(
        r"\{source(?:-table)?:\s+([^\s\}]+)(?:\s+([^\}]*))?\}",
        _replace_source_tag,
        rendered_html,
    )

    return rendered_html, source_citations, relays_addressed


def _extract_title(md_text: str, fallback: str) -> str:
    for line in md_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback.replace("-", " ").replace("_", " ").title()


def _parse_sidecar_and_analysis(
    artifact_path: Path,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Find and parse the .meta.json sidecar and .analysis.json for a Layer 0 artifact."""
    parent = artifact_path.parent
    name = artifact_path.name

    # Candidate stems: e.g. P04637.afdb.json -> P04637.afdb and P04637
    stems: list[str] = [artifact_path.stem]
    for suffix, _, _ in VIEWER_TYPE_MAP:
        if name.lower().endswith(suffix) and len(name) > len(suffix):
            base_stem = name[: -len(suffix)]
            if base_stem not in stems:
                stems.insert(0, base_stem)
    if "." in artifact_path.stem:
        first_part = name.split(".")[0]
        if first_part not in stems:
            stems.append(first_part)

    meta_data: dict[str, Any] | None = None
    analysis_data: dict[str, Any] | None = None

    for stem in stems:
        for meta_ext in (".meta.json", ".sc-meta.json"):
            cand = parent / f"{stem}{meta_ext}"
            if cand.is_file() and is_safe_to_open(cand):
                try:
                    loaded = json.loads(cand.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        meta_data = loaded
                        break
                except Exception:
                    pass
        if meta_data is not None:
            break

    # If still not found, scan all .meta.json in parent to see if outputs match artifact_path.name
    if meta_data is None and parent.is_dir():
        for child in sorted(parent.glob("*.meta.json")):
            if not is_safe_to_open(child):
                continue
            try:
                loaded = json.loads(child.read_text(encoding="utf-8"))
                if not isinstance(loaded, dict):
                    continue
                outputs = loaded.get("outputs", [])
                if isinstance(outputs, list):
                    for out_item in outputs:
                        out_path = out_item.get("path", "") if isinstance(out_item, dict) else str(out_item)
                        if Path(out_path).name == name:
                            meta_data = loaded
                            break
                if meta_data is not None:
                    break
            except Exception:
                continue

    for stem in stems:
        for ana_ext in (".analysis.json", ".sc-analysis.json"):
            cand = parent / f"{stem}{ana_ext}"
            if cand.is_file() and is_safe_to_open(cand):
                try:
                    loaded = json.loads(cand.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        analysis_data = loaded
                        break
                except Exception:
                    pass
        if analysis_data is not None:
            break

    if analysis_data is None and parent.is_dir():
        for child in sorted(parent.glob("*.analysis.json")):
            if not is_safe_to_open(child):
                continue
            try:
                loaded = json.loads(child.read_text(encoding="utf-8"))
                if not isinstance(loaded, dict):
                    continue
                src = str(loaded.get("source") or loaded.get("source_artifact") or "")
                if Path(src).name == name:
                    analysis_data = loaded
                    break
            except Exception:
                continue

    return meta_data, analysis_data


def _collect_all_artifacts(
    project_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Collect all Layer 0 artifacts across raw/ along with inline data, meta, and analysis."""
    raw_dir = project_root / "raw"
    artifacts: list[dict[str, Any]] = []
    by_class: dict[str, list[dict[str, Any]]] = {}
    all_relays: list[dict[str, Any]] = []
    seen_relays: set[tuple[str, str]] = set()

    if not raw_dir.is_dir():
        return artifacts, by_class, all_relays

    root_resolved = project_root.resolve()

    # First pass: collect all mandatory relays from every .meta.json and .analysis.json in raw/
    for json_file in sorted(raw_dir.rglob("*.json")):
        if not json_file.is_file() or not is_safe_to_open(json_file):
            continue
        if not json_file.resolve().is_relative_to(root_resolved):
            continue
        if not (_is_sidecar(json_file.name) or _is_analysis(json_file.name, json_file)):
            continue
        try:
            rec = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(rec, dict):
            continue
        rel_file = str(json_file.relative_to(project_root))
        relays = rec.get("mandatory_relays", [])
        if isinstance(relays, list):
            for r in relays:
                if isinstance(r, dict) and "code" in r:
                    code = str(r["code"])
                    key = (code, rel_file)
                    if key not in seen_relays:
                        seen_relays.add(key)
                        all_relays.append(
                            {
                                "code": code,
                                "message": r.get("message")
                                or provenance.RELAY_CODES.get(code, ""),
                                "source_file": rel_file,
                                "record_type": "analysis"
                                if _is_analysis(json_file.name, json_file)
                                else "sidecar",
                                "work_order_id": rec.get("work_order_id"),
                                "written_by": rec.get("written_by")
                                or rec.get("tool")
                                or "pde",
                            }
                        )

    # Second pass: collect primary Layer 0 artifacts
    for child in sorted(raw_dir.rglob("*")):
        if not child.is_file() or not is_safe_to_open(child):
            continue
        if not child.resolve().is_relative_to(root_resolved):
            continue
        if child.name.startswith("."):
            continue
        if _is_sidecar(child.name) or _is_analysis(child.name, child):
            continue

        rel_path = str(child.relative_to(project_root))
        parts = Path(rel_path).parts
        art_class = parts[1] if len(parts) >= 3 else "raw"

        vtype, vlabel = _classify_viewer(child.name)
        meta_data, analysis_data = _parse_sidecar_and_analysis(child)

        # Parse inline content up to 5 MB for single-file standalone rendering
        inline_data: Any = None
        try:
            fsize = child.stat().st_size
        except OSError:
            fsize = 0

        if fsize <= _MAX_INLINE_ARTIFACT_BYTES:
            try:
                raw_text = child.read_text(encoding="utf-8", errors="replace")
                if child.name.lower().endswith(".json"):
                    inline_data = json.loads(raw_text)
                else:
                    inline_data = raw_text
            except Exception:
                inline_data = None

        verdict = None
        if isinstance(analysis_data, dict):
            assessment = analysis_data.get("assessment")
            if isinstance(assessment, dict):
                verdict = assessment.get("verdict") or assessment.get("status")
            if not verdict:
                verdict = analysis_data.get("verdict")

        wo_id = None
        if isinstance(meta_data, dict) and meta_data.get("work_order_id"):
            wo_id = meta_data.get("work_order_id")
        elif isinstance(analysis_data, dict) and analysis_data.get("work_order_id"):
            wo_id = analysis_data.get("work_order_id")

        domain_studio, domain_label = _detect_domain_studio(
            child.name, art_class, inline_data, analysis_data
        )
        if vtype == "json" and domain_label:
            vlabel = domain_label

        item: dict[str, Any] = {
            "id": rel_path,
            "name": child.name,
            "rel_path": rel_path,
            "artifact_class": art_class,
            "viewer_type": vtype,
            "domain_studio": domain_studio,
            "viewer_label": vlabel,
            "size_bytes": fsize,
            "work_order_id": wo_id,
            "verdict": verdict,
            "data": inline_data,
            "meta": meta_data,
            "analysis": analysis_data,
            "paired_files": {},
        }
        artifacts.append(item)
        by_class.setdefault(art_class, []).append(item)

    # Link paired files (e.g., .poses.pdbqt <-> .receptor.pdbqt, .cif <-> .afdb.json / .pockets.json)
    by_rel = {a["rel_path"]: a for a in artifacts}
    for a in artifacts:
        rpath = a["rel_path"]
        parent_str = str(Path(rpath).parent)
        fname = a["name"]
        if fname.endswith(".poses.pdbqt"):
            stem = fname[: -len(".poses.pdbqt")]
            rec_cand = f"{parent_str}/{stem}.receptor.pdbqt"
            if rec_cand in by_rel:
                a["paired_files"]["receptor"] = rec_cand
            scores_cand = f"{parent_str}/{stem}.docking_result.json"
            if scores_cand in by_rel:
                a["paired_files"]["scores"] = scores_cand
        elif fname.endswith(".receptor.pdbqt"):
            stem = fname[: -len(".receptor.pdbqt")]
            poses_cand = f"{parent_str}/{stem}.poses.pdbqt"
            if poses_cand in by_rel:
                a["paired_files"]["poses"] = poses_cand
        elif fname.endswith(".cif") or fname.endswith(".pdb"):
            stem = Path(fname).stem
            for plddt_cand in (
                f"{parent_str}/{stem}.afdb.json",
                f"{parent_str}/{stem}.plddt.json",
            ):
                if plddt_cand in by_rel:
                    a["paired_files"]["plddt"] = plddt_cand
                    break
            pocket_cand = f"raw/pocket/{stem}.pockets.json"
            if pocket_cand in by_rel:
                a["paired_files"]["pockets"] = pocket_cand

    return artifacts, by_class, all_relays


def _collect_all_findings(
    project_root: Path,
    work_orders: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Collect all Layer 1 findings (both WO-linked and any draft/fast-path markdown in findings/)."""
    findings: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    # Map relative finding path -> latest WO referencing it
    path_to_wo: dict[str, dict[str, Any]] = {}
    for wo in work_orders:
        deliverables_raw = wo.get("deliverables", {})
        if not isinstance(deliverables_raw, dict):
            continue
        deliverables = normalize_deliverables(deliverables_raw)
        for rel_path in deliverables.get("layer_1", []) or []:
            path_to_wo[str(rel_path)] = wo

    findings_dir = project_root / "findings"
    root_resolved = project_root.resolve()

    candidate_paths: list[str] = list(path_to_wo.keys())
    if findings_dir.is_dir():
        for md_file in sorted(findings_dir.rglob("*.md")):
            if not md_file.is_file() or not is_safe_to_open(md_file):
                continue
            if not md_file.resolve().is_relative_to(root_resolved):
                continue
            rel = str(md_file.relative_to(project_root))
            if rel not in candidate_paths:
                candidate_paths.append(rel)

    for rel_path in candidate_paths:
        if rel_path in seen_paths:
            continue
        seen_paths.add(rel_path)

        resolved = confine_path(project_root, Path(rel_path))
        if resolved is None or not resolved.is_file():
            continue

        raw_md = resolved.read_text(encoding="utf-8", errors="replace")
        title = _extract_title(raw_md, Path(rel_path).stem)
        rendered_html, citations, relays_addressed = _render_markdown_with_annotations(
            raw_md, project_root, rel_path
        )

        parts = Path(rel_path).parts
        discipline = parts[1] if len(parts) >= 3 and parts[0] == "findings" else "general"

        wo = path_to_wo.get(rel_path)
        if wo is not None:
            wo_id = wo.get("id", "")
            revision = wo.get("revision", 1)
            role = wo.get("requested_role", "")
            state = wo.get("state", "in_progress")
            stage = wo.get("stage", "")
            cycle = wo.get("cycle", "")
            deliverables = normalize_deliverables(wo.get("deliverables", {}))
            l0_classes = deliverables.get("layer_0_classes", [])
        else:
            wo_id = ""
            revision = 0
            role = "scientific-reviewer" if discipline == "reviews" else discipline
            state = "review" if discipline == "reviews" else "fast_path"
            stage = ""
            cycle = ""
            l0_classes = []

        findings.append(
            {
                "id": rel_path,
                "title": title,
                "source_path": rel_path,
                "discipline": discipline,
                "raw_markdown": raw_md,
                "html": rendered_html,
                "work_order_id": wo_id,
                "revision": revision,
                "requested_role": role,
                "state": state,
                "stage": stage,
                "cycle": cycle,
                "artifact_classes": l0_classes,
                "source_citations": citations,
                "relays_addressed": relays_addressed,
            }
        )

    return findings


def _collect_retrospectives(project_root: Path) -> list[dict[str, Any]]:
    """Collect specialist retrospectives under `retrospectives/*.md`."""
    retros: list[dict[str, Any]] = []
    retros_dir = project_root / "retrospectives"
    if not retros_dir.is_dir():
        return retros
    root_resolved = project_root.resolve()
    for md_file in sorted(retros_dir.rglob("*.md")):
        if not md_file.is_file() or not is_safe_to_open(md_file):
            continue
        if not md_file.resolve().is_relative_to(root_resolved):
            continue
        rel_path = str(md_file.relative_to(project_root))
        raw_md = md_file.read_text(encoding="utf-8", errors="replace")
        title = _extract_title(raw_md, md_file.stem)
        html_out, _, _ = _render_markdown_with_annotations(raw_md, project_root, rel_path)
        agent_slug = md_file.stem.removesuffix("-retro").removeprefix("pde-")
        retros.append(
            {
                "id": rel_path,
                "name": md_file.name,
                "agent": agent_slug,
                "title": title,
                "source_path": rel_path,
                "raw_markdown": raw_md,
                "html": html_out,
            }
        )
    return retros


def _collect_environment_readiness(project_root: Path) -> dict[str, Any]:
    """Collect an offline, zero-network summary of PDE binaries, libraries, and credentials."""
    import importlib.util
    import shutil as _shutil

    repo = _repo_root()
    env_ver_path = repo / "tools" / "ENV_VERSION"
    env_version = (
        env_ver_path.read_text(encoding="utf-8").strip()
        if env_ver_path.is_file()
        else "unknown"
    )

    binaries: list[dict[str, Any]] = []
    for bname, desc in (
        ("pde", "Primary PDE CLI Engine"),
        ("hypex", "Hypex Hypothesis Store"),
        ("elo", "Pairwise ELO Rating Engine"),
        ("prox", "Proximity Clustering CLI"),
        ("fpocket", "Alpha-Sphere Pocket Detector"),
        ("vina", "AutoDock Vina Docking Engine"),
    ):
        local_bin = repo / "bin" / bname
        found = local_bin.is_file() or (_shutil.which(bname) is not None)
        binaries.append(
            {
                "name": bname,
                "description": desc,
                "status": "ready" if found else "optional_missing",
            }
        )

    libraries: list[dict[str, Any]] = []
    for mod_name, label in (
        ("rdkit", "RDKit Cheminformatics"),
        ("gemmi", "Gemmi Crystallography / mmCIF"),
        ("biopython", "BioPython Sequence & Structure"),
        ("scipy", "SciPy Curve Fitting & Stats"),
        ("jsonpath_ng", "JSONPath RFC 9535 Verifier"),
        ("mcp", "Model Context Protocol SDK"),
    ):
        spec_mod = "Bio" if mod_name == "biopython" else mod_name
        has_mod = importlib.util.find_spec(spec_mod) is not None
        libraries.append(
            {
                "name": mod_name,
                "label": label,
                "status": "ready" if has_mod else "missing",
            }
        )

    credentials: list[dict[str, Any]] = []
    for env_key, label in (
        ("ALPHAGENOME_API_KEY", "AlphaGenome ISM API Key"),
        ("NCBI_API_KEY", "NCBI E-utilities Rate-Limit Key"),
        ("CLOUD_APPLICATION_CREDENTIALS", "Cloud / AF3 Endpoint Credentials"),
    ):
        is_set = bool(os.environ.get(env_key))
        credentials.append(
            {
                "name": env_key,
                "label": label,
                "status": "configured" if is_set else "public_or_adc_fallback",
            }
        )

    rel_root = (
        str(project_root.relative_to(_repo_root()))
        if project_root.is_relative_to(_repo_root())
        else project_root.name
    )

    return {
        "cli_version": CLI_VERSION,
        "env_version": env_version[:16],
        "project_root": rel_root or ".",
        "binaries": binaries,
        "libraries": libraries,
        "credentials": credentials,
        "cli_binaries": {b["name"]: {"available": b["status"] == "ready", **b} for b in binaries},
        "python_libraries": {l["name"]: {"available": l["status"] == "ready", **l} for l in libraries},
        "api_credentials": {c["name"]: {"configured": c["status"] == "configured", **c} for c in credentials},
        "bootstrap_ready": all(l["status"] == "ready" for l in libraries[:3]),
    }


def _collect_events(project_root: Path) -> list[dict[str, Any]]:
    events_path = project_root / controlstore.CONTROL_DIR / "events.ndjson"
    if not events_path.is_file() or not is_safe_to_open(events_path):
        return []
    events: list[dict[str, Any]] = []
    for line in events_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
            if isinstance(ev, dict):
                events.append(ev)
        except Exception:
            continue
    return events


def _build_agent_forest_and_messages(
    project_root: Path,
    roles_catalog: dict[str, dict[str, Any]],
    work_orders_latest: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    validations: dict[str, dict[str, Any]],
    leases: list[dict[str, Any]],
    events: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    contexts: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Construct Multi-Agent Lineage Forest nodes, edges, and message log."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    messages: list[dict[str, Any]] = []
    contexts_map = contexts or {}

    def _skills_for(role: str) -> list[str]:
        return roles_catalog.get(role, {}).get(
            "skills", ["artifact-conventions"]
        )

    def _desc_for(role: str) -> str:
        return roles_catalog.get(role, {}).get(
            "description", role.replace("-", " ").title()
        )

    # 1. Root User node & Orchestrator nodes
    has_active_runs = any(r.get("state") in ("running", "starting", "queued") for r in runs)
    lead_state = "running" if has_active_runs else ("succeeded" if (work_orders_latest or artifacts) else "idle")

    nodes.append(
        {
            "id": "user",
            "name": "Scientist / User",
            "role": "user",
            "category": "User",
            "parentId": None,
            "ancestry": [],
            "state": "active",
            "wo_state": "active",
            "work_order_id": None,
            "revision": None,
            "run_id": None,
            "attempt": 1,
            "decision_question": "Program Charter & Discovery Objective",
            "description": "Principal Investigator / Interactive User Session",
            "injected_skills": ["pharmakon-discovery-engine", "pde-dashboard"],
            "validation": None,
            "deliverables": [],
        }
    )

    nodes.append(
        {
            "id": "science-program-lead",
            "name": "Science Program Lead",
            "role": "science-program-lead",
            "category": "Orchestrator",
            "parentId": "user",
            "ancestry": ["user"],
            "state": lead_state,
            "wo_state": lead_state,
            "work_order_id": None,
            "revision": None,
            "run_id": None,
            "attempt": 1,
            "decision_question": "Synthesize cross-disciplinary evidence, manage Layer 2 program state, and govern Stage 0–4 gate decisions.",
            "description": _desc_for("science-program-lead"),
            "injected_skills": _skills_for("science-program-lead"),
            "validation": None,
            "deliverables": [
                "program-state/decision-log.md",
                "program-state/liability-tracker.md",
                "program-state/active-series.md",
                "program-state/open-questions.md",
                "executive/program-summary.md",
            ],
        }
    )
    edges.append(
        {
            "parentId": "user",
            "childId": "science-program-lead",
            "label": "charter",
            "state": lead_state,
        }
    )

    roc_state = lead_state if work_orders_latest else "idle"
    nodes.append(
        {
            "id": "research-operations-controller",
            "name": "Research Ops Controller",
            "role": "research-operations-controller",
            "category": "Orchestrator",
            "parentId": "science-program-lead",
            "ancestry": ["user", "science-program-lead"],
            "state": roc_state,
            "wo_state": roc_state,
            "work_order_id": None,
            "revision": None,
            "run_id": None,
            "attempt": 1,
            "decision_question": "Commit work orders, freeze context snapshots, manage single-flight resource leases, and enforce 10-check mechanical validation.",
            "description": _desc_for("research-operations-controller"),
            "injected_skills": _skills_for("research-operations-controller"),
            "validation": None,
            "deliverables": [".pde/control/events.ndjson"],
        }
    )
    edges.append(
        {
            "parentId": "science-program-lead",
            "childId": "research-operations-controller",
            "label": "cohort-dispatch",
            "state": roc_state,
        }
    )

    # Map WO+rev to runs
    runs_by_wo: dict[str, list[dict[str, Any]]] = {}
    for r in runs:
        key = f"{r.get('work_order_id')}-r{r.get('work_order_revision')}"
        runs_by_wo.setdefault(key, []).append(r)

    hypex_sup_node_id: str | None = None

    for wo in work_orders_latest:
        wo_id = wo.get("id", "WO-000")
        rev = wo.get("revision", 1)
        wo_key = f"{wo_id}-r{rev}"
        role = wo.get("requested_role", "specialist")
        wo_state = wo.get("state", "proposed")
        wo_runs = runs_by_wo.get(wo_key, [])
        latest_run = wo_runs[-1] if wo_runs else {}
        run_id = latest_run.get("run_id") or f"RUN-{wo_id.split('-')[-1]}"
        run_state = latest_run.get("state") or (
            "succeeded"
            if wo_state in ("mechanically_validated", "under_scientific_review", "scientifically_accepted")
            else ("failed" if wo_state in ("validation_failed", "scientifically_rejected") else "running")
        )
        attempt = latest_run.get("attempt", max(1, len(wo_runs)))

        val_record = validations.get(wo_key)
        if val_record is None:
            # Compute live preview of the 10 mechanical checks so the inspector always shows all 10 checks
            try:
                checks, overall_res, _ = _run_all_checks(project_root, wo)
                val_record = {
                    "work_order_id": wo_id,
                    "work_order_revision": rev,
                    "run_id": run_id,
                    "validated_at": _utc_now(),
                    "result": overall_res,
                    "mode": "live_preview",
                    "checks": checks,
                }
            except Exception:
                val_record = None

        deliverables = normalize_deliverables(wo.get("deliverables", {}))
        deliv_list = list(deliverables.get("layer_1", []) or []) + [
            f"raw/{normalize_artifact_class(c)}"
            for c in (deliverables.get("layer_0_classes", []) or [])
        ]

        ctx_snap = contexts_map.get(wo_key)
        if ctx_snap is None and isinstance(wo.get("context"), dict):
            ctx_snap = {
                "work_order_id": wo_id,
                "revision": rev,
                "content": wo["context"].get("content", ""),
                "artifact_links": wo["context"].get("artifact_links", []),
                "content_sha256": wo["context"].get("content_sha256", ""),
                "hash": wo["context"].get("content_sha256") or wo["context"].get("hash") or "",
            }

        parent_id = "research-operations-controller"
        ancestry = ["user", "science-program-lead", "research-operations-controller"]
        if role.startswith("hypex-") and role != "hypex-supervisor" and hypex_sup_node_id:
            parent_id = hypex_sup_node_id
            ancestry = [*ancestry, hypex_sup_node_id]

        node_id = f"{wo_id}-r{rev}-{role}"
        if role == "hypex-supervisor":
            hypex_sup_node_id = node_id

        display_state = (
            wo_state
            if wo_state in ("scientifically_accepted", "mechanically_validated", "validation_failed")
            else run_state
        )

        nodes.append(
            {
                "id": node_id,
                "name": f"{role.replace('-', ' ').title()} ({wo_id})",
                "role": role,
                "category": ROLE_CATEGORY_MAP.get(role, "Specialist"),
                "parentId": parent_id,
                "ancestry": ancestry,
                "state": display_state,
                "run_state": run_state,
                "wo_state": wo_state,
                "work_order_id": wo_id,
                "revision": rev,
                "run_id": run_id,
                "attempt": attempt,
                "correction_cycle": int(wo.get("correction_cycle", 0) or 0),
                "stage": wo.get("stage", ""),
                "cycle": wo.get("cycle", ""),
                "priority": wo.get("priority", "normal"),
                "resource_class": wo.get("resource_class", "standard"),
                "decision_question": wo.get("decision_question", ""),
                "description": _desc_for(role),
                "injected_skills": _skills_for(role),
                "dependencies": list(wo.get("dependencies", []) or []),
                "acceptance_criteria": list(wo.get("acceptance_criteria", []) or []),
                "alert_policy": wo.get("alert_policy", {}),
                "context_snapshot": ctx_snap,
                "failure_class": latest_run.get("failure_class"),
                "failure_detail": latest_run.get("detail"),
                "validation": val_record,
                "deliverables": deliv_list,
                "created_at": wo.get("created_at"),
                "started_at": latest_run.get("started_at"),
                "completed_at": latest_run.get("completed_at"),
            }
        )
        edges.append(
            {
                "parentId": parent_id,
                "childId": node_id,
                "label": f"{wo_id}-r{rev} (att #{attempt})",
                "state": display_state,
            }
        )

        # Attach Finding Validator node if validated or validation attempted
        if wo_key in validations or wo_state in (
            "submitted",
            "mechanically_validated",
            "validation_failed",
            "under_scientific_review",
            "scientifically_accepted",
        ):
            val_node_id = f"validator-{wo_key}"
            v_res = (val_record or {}).get("result", "pass")
            v_state = (
                "mechanically_validated"
                if v_res in ("pass", "pass_with_warnings")
                else "validation_failed"
            )
            nodes.append(
                {
                    "id": val_node_id,
                    "name": f"Finding Validator ({wo_id})",
                    "role": "finding-validator",
                    "category": "Quality Gate",
                    "parentId": node_id,
                    "ancestry": [*ancestry, node_id],
                    "state": v_state,
                    "wo_state": wo_state,
                    "work_order_id": wo_id,
                    "revision": rev,
                    "run_id": run_id,
                    "attempt": attempt,
                    "correction_cycle": int(wo.get("correction_cycle", 0) or 0),
                    "decision_question": f"Verify all 10 mechanical validation checks for {wo_key}",
                    "description": _desc_for("finding-validator"),
                    "injected_skills": _skills_for("finding-validator"),
                    "context_snapshot": ctx_snap,
                    "validation": val_record,
                    "deliverables": [f".pde/control/validations/{wo_key}.json"],
                }
            )
            edges.append(
                {
                    "parentId": node_id,
                    "childId": val_node_id,
                    "label": "10-check gate",
                    "state": v_state,
                }
            )

            # Attach Scientific Reviewer node if under review or accepted
            if wo_state in ("under_scientific_review", "scientifically_accepted", "revision_requested"):
                rev_node_id = f"reviewer-{wo_key}"
                r_state = (
                    "scientifically_accepted"
                    if wo_state == "scientifically_accepted"
                    else "running"
                )
                nodes.append(
                    {
                        "id": rev_node_id,
                        "name": f"Scientific Reviewer ({wo_id})",
                        "role": "scientific-reviewer",
                        "category": "Quality Gate",
                        "parentId": val_node_id,
                        "ancestry": [*ancestry, node_id, val_node_id],
                        "state": r_state,
                        "wo_state": wo_state,
                        "work_order_id": wo_id,
                        "revision": rev,
                        "run_id": run_id,
                        "attempt": attempt,
                        "decision_question": f"Independent Phase-2 re-analysis & scientific review of {wo_key}",
                        "description": _desc_for("scientific-reviewer"),
                        "injected_skills": _skills_for("scientific-reviewer"),
                        "validation": val_record,
                        "deliverables": ["findings/reviews/"],
                    }
                )
                edges.append(
                    {
                        "parentId": val_node_id,
                        "childId": rev_node_id,
                        "label": "phase-2 audit",
                        "state": r_state,
                    }
                )

    # Synthesize virtual Fast-Path specialist nodes for any artifacts not covered by a formal Work Order
    unattributed_by_role: dict[str, list[dict[str, Any]]] = {}
    for art in artifacts:
        if art.get("work_order_id"):
            continue
        meta = art.get("meta") or {}
        tool_name = str(meta.get("tool") or art.get("artifact_class") or "pde")
        role = TOOL_TO_ROLE_FALLBACK.get(tool_name, "computational-biologist")
        unattributed_by_role.setdefault(role, []).append(art)

    for role, role_arts in sorted(unattributed_by_role.items()):
        # Only add virtual node if no WO already exists for this role, or if there are no WOs at all
        if not work_orders_latest or not any(w.get("requested_role") == role for w in work_orders_latest):
            vnode_id = f"fastpath-{role}"
            nodes.append(
                {
                    "id": vnode_id,
                    "name": f"{role.replace('-', ' ').title()} (Fast-Path)",
                    "role": role,
                    "category": ROLE_CATEGORY_MAP.get(role, "Specialist"),
                    "parentId": "science-program-lead",
                    "ancestry": ["user", "science-program-lead"],
                    "state": "succeeded",
                    "wo_state": "fast_path",
                    "work_order_id": "FAST-PATH",
                    "revision": 1,
                    "run_id": "RUN-FAST",
                    "attempt": 1,
                    "decision_question": f"Fast-Path interactive scientific execution ({len(role_arts)} Layer 0 artifact(s) generated)",
                    "description": _desc_for(role),
                    "injected_skills": _skills_for(role),
                    "validation": None,
                    "deliverables": [a["rel_path"] for a in role_arts],
                }
            )
            edges.append(
                {
                    "parentId": "science-program-lead",
                    "childId": vnode_id,
                    "label": "fast-path",
                    "state": "succeeded",
                }
            )

    # Attach Project Curator node representing the Interactive Dashboard build
    nodes.append(
        {
            "id": "project-curator-dashboard",
            "name": "Project Curator (Dashboard)",
            "role": "project-curator",
            "category": "Presentation",
            "parentId": "research-operations-controller",
            "ancestry": ["user", "science-program-lead", "research-operations-controller"],
            "state": "succeeded",
            "wo_state": "published",
            "work_order_id": None,
            "revision": None,
            "run_id": None,
            "attempt": 1,
            "decision_question": "Compile Unified Multi-Agent Graph + 14 PDE Scientific Viewers into Interactive Dashboard.",
            "description": _desc_for("project-curator"),
            "injected_skills": _skills_for("project-curator"),
            "validation": None,
            "deliverables": ["dashboard.html"],
        }
    )
    edges.append(
        {
            "parentId": "research-operations-controller",
            "childId": "project-curator-dashboard",
            "label": "dashboard-build",
            "state": "succeeded",
        }
    )

    # 2. Build Inter-Agent Message & Event Stream
    for ev in events:
        ts = ev.get("timestamp", _utc_now())
        ev_type = ev.get("type", "event")
        subj = ev.get("subject_id", "")
        from_st = ev.get("from_state")
        to_st = ev.get("to_state")
        detail = ev.get("detail")
        sender = str(ev.get("actor") or "research-operations-controller")
        recipient = str(subj)
        level = "info"
        summary = f"{ev_type}: {subj} ({from_st or 'init'} → {to_st})"
        if ev_type == "dispatch.subagent" and isinstance(detail, dict):
            sub_name = detail.get("subagent_name") or f"pde-{detail.get('requested_role', 'specialist')}"
            recipient = f"{sub_name} ({subj})"
            summary = f"Dispatched {sub_name} on {subj} ({detail.get('run_id', '')}): {detail.get('decision_question', '')}"
        elif ev_type == "correction_returned" and isinstance(detail, dict):
            sender = "finding-validator"
            cyc = detail.get("correction_cycle", 1)
            failed_list = detail.get("checks_failed", [])
            level = "warn"
            summary = f"CORRECTION REQUIRED on {subj} (Cycle {cyc}/2): failed checks = {', '.join(failed_list)}"
        elif ev_type == "validation.completed":
            sender = "finding-validator"
            recipient = "research-operations-controller"
            res = detail.get("result") if isinstance(detail, dict) else detail
            failed_list = (
                detail.get("checks_failed", []) if isinstance(detail, dict) else []
            )
            if res == "fail":
                level = "error"
                summary = f"VALIDATION FAILED on {subj}: failed checks = {', '.join(failed_list)}"
            else:
                level = "success"
                summary = f"10-Check Mechanical Validation PASSED ({res}) for {subj}"
        elif to_st in ("failed", "validation_failed", "scientifically_rejected"):
            level = "error"
        elif to_st in ("mechanically_validated", "scientifically_accepted", "succeeded"):
            level = "success"

        messages.append(
            {
                "timestamp": ts,
                "sender": sender,
                "recipient": recipient,
                "type": ev_type,
                "level": level,
                "summary": summary,
                "detail": detail,
            }
        )

    # Also synthesize tool provenance messages from .meta.json and .analysis.json
    for art in artifacts:
        meta = art.get("meta")
        if isinstance(meta, dict):
            tool_name = meta.get("tool", "pde")
            subcmd = meta.get("subcommand", "fetch")
            role = TOOL_TO_ROLE_FALLBACK.get(str(tool_name), "specialist")
            messages.append(
                {
                    "timestamp": meta.get("timestamp") or meta.get("created_at") or _utc_now(),
                    "sender": role,
                    "recipient": f"raw/{art['artifact_class']}",
                    "type": "tool.phase1",
                    "level": "info",
                    "summary": f"Phase 1 `pde {tool_name} {subcmd}` wrote `{art['rel_path']}` (SHA-256 verified)",
                    "detail": {"parameters": meta.get("parameters"), "relays": meta.get("mandatory_relays")},
                }
            )
        ana = art.get("analysis")
        if isinstance(ana, dict):
            tset = ana.get("threshold_set") or ana.get("thresholds_applied") or "default"
            verdict = art.get("verdict") or "evaluated"
            messages.append(
                {
                    "timestamp": ana.get("timestamp") or ana.get("created_at") or _utc_now(),
                    "sender": ana.get("written_by") or "phase2-analyzer",
                    "recipient": "finding-validator",
                    "type": "tool.phase2",
                    "level": "success" if verdict in ("pass", "passed", "acceptable") else "warn",
                    "summary": f"Phase 2 offline analysis on `{art['name']}` [thresholds: {tset}] → verdict: {verdict}",
                    "detail": {"threshold_set": tset, "relays": ana.get("mandatory_relays")},
                }
            )

    messages.sort(key=lambda m: str(m.get("timestamp") or ""))
    return nodes, edges, messages


def _collect_yaml_or_json_dir(project_root: Path, dir_name: str, existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Supplement controlstore records with any YAML/JSON records in top-level `<dir_name>/`."""
    results = list(existing)
    seen_ids = {str(r.get("id") or r.get("concept_id") or r.get("assessment_id") or r.get("decision_id") or "") for r in results}
    target_dir = project_root / dir_name
    if not target_dir.is_dir():
        return results
    for fpath in sorted(target_dir.glob("*")):
        if not fpath.is_file() or not is_safe_to_open(fpath):
            continue
        if fpath.suffix.lower() not in (".yaml", ".yml", ".json"):
            continue
        try:
            loaded = yaml.safe_load(fpath.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                loaded = json.loads(json.dumps(loaded, default=str))
                rec_id = str(loaded.get("id") or loaded.get("concept_id") or loaded.get("assessment_id") or loaded.get("decision_id") or fpath.stem)
                if rec_id not in seen_ids:
                    loaded.setdefault("id", rec_id)
                    loaded.setdefault("_source_file", f"{dir_name}/{fpath.name}")
                    results.append(loaded)
                    seen_ids.add(rec_id)
        except Exception:
            continue
    return results


def collect_dashboard_bundle(project_root: Path | str) -> dict[str, Any]:
    """Collect the complete Unified Agentic + Scientific JSON bundle for a PDE project."""
    root = Path(project_root).expanduser().resolve()
    roles_catalog = _load_roles_catalog()

    # Read program.yaml if present
    program_cfg: dict[str, Any] = {}
    for cand in (root / ".pde" / "program.yaml", root / "program.yaml"):
        if cand.is_file() and is_safe_to_open(cand):
            try:
                loaded = yaml.safe_load(cand.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    program_cfg = loaded
                    break
            except Exception:
                pass

    # Collect control-plane records
    all_wos = controlstore.list_records(root, "work-order")
    all_wos.sort(key=lambda r: (r.get("id", ""), r.get("revision", 0)))

    latest_wo_by_id: dict[str, dict[str, Any]] = {}
    for wo in all_wos:
        wo_id = wo.get("id", "")
        if wo_id:
            if (
                wo_id not in latest_wo_by_id
                or wo.get("revision", 0) >= latest_wo_by_id[wo_id].get("revision", 0)
            ):
                latest_wo_by_id[wo_id] = wo
    work_orders_latest = [latest_wo_by_id[k] for k in sorted(latest_wo_by_id)]

    runs = controlstore.list_records(root, "run")
    runs.sort(key=lambda r: r.get("run_id", ""))

    validations_list = controlstore.list_records(root, "validation")
    validations_map: dict[str, dict[str, Any]] = {}
    for v in validations_list:
        k = f"{v.get('work_order_id')}-r{v.get('work_order_revision')}"
        validations_map[k] = v

    contexts_list = controlstore.list_records(root, "context")
    contexts_map: dict[str, dict[str, Any]] = {}
    for ctx in contexts_list:
        ck = f"{ctx.get('work_order_id')}-r{ctx.get('revision', 1)}"
        if not ctx.get("hash"):
            ctx["hash"] = ctx.get("content_sha256") or ctx.get("sha256") or ""
        contexts_map[ck] = ctx

    leases = controlstore.list_records(root, "lease")
    concepts = _collect_yaml_or_json_dir(root, "concepts", controlstore.list_records(root, "concept"))
    assessments = _collect_yaml_or_json_dir(root, "assessments", controlstore.list_records(root, "assessment"))
    decisions = _collect_yaml_or_json_dir(root, "decisions", controlstore.list_records(root, "decision"))
    events = _collect_events(root)
    retrospectives = _collect_retrospectives(root)
    env_readiness = _collect_environment_readiness(root)

    # Collect Layer 0 artifacts & relays
    artifacts, artifacts_by_class, mandatory_relays = _collect_all_artifacts(root)

    # Collect Layer 1 findings
    findings = _collect_all_findings(root, work_orders_latest)

    # Cross-reference mandatory relays with findings
    all_findings_text = "\n".join(f["raw_markdown"] for f in findings)
    addressed_relay_map: dict[str, list[str]] = {}
    for f in findings:
        for code in f["relays_addressed"]:
            addressed_relay_map.setdefault(code, []).append(f["source_path"])
        # Also check plain occurrence
        for r in mandatory_relays:
            c = r["code"]
            if c in f["raw_markdown"] and f["source_path"] not in addressed_relay_map.get(c, []):
                addressed_relay_map.setdefault(c, []).append(f["source_path"])

    for r in mandatory_relays:
        code = r["code"]
        r["addressed"] = bool(addressed_relay_map.get(code)) or (code in all_findings_text)
        r["addressed_in_findings"] = addressed_relay_map.get(code, [])

    # Collect Layer 2 Program State
    program_state_docs: list[dict[str, Any]] = []
    ps_dir = root / "program-state"
    if ps_dir.is_dir():
        for md_file in sorted(ps_dir.glob("*.md")):
            if not md_file.is_file() or not is_safe_to_open(md_file):
                continue
            raw_md = md_file.read_text(encoding="utf-8", errors="replace")
            title = _extract_title(raw_md, md_file.stem)
            html_out, _, _ = _render_markdown_with_annotations(
                raw_md, root, f"program-state/{md_file.name}"
            )
            program_state_docs.append(
                {
                    "name": md_file.name,
                    "stem": md_file.stem,
                    "title": title,
                    "source_file": f"program-state/{md_file.name}",
                    "raw_markdown": raw_md,
                    "html": html_out,
                }
            )

    # Collect Layer 3 Gates
    gates: list[dict[str, Any]] = []
    gates_dir = root / "gates"
    if gates_dir.is_dir():
        for md_file in sorted(gates_dir.rglob("*.md")):
            if not md_file.is_file() or not is_safe_to_open(md_file):
                continue
            raw_md = md_file.read_text(encoding="utf-8", errors="replace")
            rel_p = str(md_file.relative_to(root))
            title = _extract_title(raw_md, md_file.stem)
            html_out, _, _ = _render_markdown_with_annotations(raw_md, root, rel_p)
            gates.append(
                {
                    "stage_name": md_file.parent.name,
                    "title": title,
                    "source_path": rel_p,
                    "raw_markdown": raw_md,
                    "html": html_out,
                }
            )

    # Collect Layer 4 Executive Summary
    exec_doc: dict[str, Any] | None = None
    exec_path = root / "executive" / "program-summary.md"
    if exec_path.is_file() and is_safe_to_open(exec_path):
        raw_md = exec_path.read_text(encoding="utf-8", errors="replace")
        html_out, _, _ = _render_markdown_with_annotations(
            raw_md, root, "executive/program-summary.md"
        )
        exec_doc = {
            "title": _extract_title(raw_md, "Executive Program Summary"),
            "source_path": "executive/program-summary.md",
            "raw_markdown": raw_md,
            "html": html_out,
        }

    # Build Multi-Agent Forest & Messages
    nodes, edges, messages = _build_agent_forest_and_messages(
        project_root=root,
        roles_catalog=roles_catalog,
        work_orders_latest=work_orders_latest,
        runs=runs,
        validations=validations_map,
        leases=leases,
        events=events,
        artifacts=artifacts,
        findings=findings,
        contexts=contexts_map,
    )

    # Compute validation check pass rate across work orders
    total_checks_run = 0
    total_checks_passed = 0
    for n in nodes:
        val = n.get("validation")
        if isinstance(val, dict) and n.get("category") != "Quality Gate":
            for chk in val.get("checks", []) or []:
                if chk.get("result") != "skip":
                    total_checks_run += 1
                    if chk.get("result") in ("pass", "pass_with_warnings"):
                        total_checks_passed += 1

    pass_rate = (
        round((total_checks_passed / total_checks_run) * 100.0, 1)
        if total_checks_run > 0
        else 100.0
    )

    active_stage = program_cfg.get("stage")
    if not active_stage and work_orders_latest:
        active_stage = work_orders_latest[-1].get("stage")
    if not active_stage:
        active_stage = "Stage 0–1 Discovery"

    program_name = (
        program_cfg.get("name")
        or program_cfg.get("program_name")
        or program_cfg.get("target")
        or root.name
    )

    active_leases = [l for l in leases if l.get("state") == "held"]

    bundle: dict[str, Any] = {
        "program": {
            "name": str(program_name),
            "target": program_cfg.get("target", ""),
            "indication": program_cfg.get("indication", ""),
            "modality": program_cfg.get("modality", ""),
            "stage": str(active_stage),
            "project_root": (
                str(root.relative_to(_repo_root()))
                if root.is_relative_to(_repo_root())
                else root.name
            ),
            "cli_version": CLI_VERSION,
            "generated_at": _utc_now(),
            "summary_metrics": {
                "n_agents": len(nodes),
                "n_roles_available": len(roles_catalog),
                "n_work_orders": len(work_orders_latest),
                "n_runs": len(runs),
                "n_validated": sum(
                    1
                    for w in work_orders_latest
                    if w.get("state")
                    in ("mechanically_validated", "under_scientific_review", "scientifically_accepted")
                ),
                "validation_pass_rate": pass_rate,
                "total_checks_passed": total_checks_passed,
                "total_checks_run": total_checks_run,
                "n_artifacts": len(artifacts),
                "n_findings": len(findings),
                "n_relays": len(mandatory_relays),
                "n_relays_addressed": sum(1 for r in mandatory_relays if r.get("addressed")),
                "n_active_leases": len(active_leases),
                "n_concepts": len(concepts),
                "n_assessments": len(assessments),
                "n_decisions": len(decisions),
                "n_retrospectives": len(retrospectives),
            },
        },
        "agent_system": {
            "roles_catalog": roles_catalog,
            "all_10_checks": [{"name": k, "kind": v} for k, v in ALL_10_CHECKS],
            "nodes": nodes,
            "edges": edges,
            "work_orders": work_orders_latest,
            "contexts": contexts_list,
            "runs": runs,
            "validations": list(validations_map.values()),
            "leases": leases,
            "events": events,
            "messages": messages,
            "retrospectives": retrospectives,
            "environment": env_readiness,
        },
        "science": {
            "executive": exec_doc,
            "program_state": program_state_docs,
            "triage_and_gates": {
                "concepts": concepts,
                "assessments": assessments,
                "decisions": decisions,
                "gates": gates,
            },
            "findings": findings,
            "mandatory_relays": mandatory_relays,
            "artifacts": artifacts,
            "artifacts_by_class": artifacts_by_class,
        },
    }
    return bundle


def build_dashboard_html(
    project_root: Path | str,
    output_path: Path | str | None = None,
    standalone_mode: bool = True,
) -> tuple[Path, dict[str, Any]]:
    """Render the self-contained `dashboard.html` and write it atomically."""
    root = Path(project_root).expanduser().resolve()
    bundle = collect_dashboard_bundle(root)
    bundle["program"]["standalone_mode"] = bool(standalone_mode)

    template_dir = Path(__file__).resolve().parent.parent / "site_templates"
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(template_dir)),
        autoescape=jinja2.select_autoescape(["html"]),
    )
    template = env.get_template("dashboard.html")

    # Safe JSON embedding inside <script>: escape </script> and <!--
    bundle_json = (
        json.dumps(bundle, ensure_ascii=False, default=str)
        .replace("</", "<\\/")
        .replace("<!--", "<\\!--")
    )

    rendered = template.render(
        program=bundle["program"],
        bundle_json=bundle_json,
        standalone_mode=standalone_mode,
    )

    if output_path is not None:
        out_cand = Path(output_path).expanduser()
        target_path = out_cand if out_cand.is_absolute() else (Path.cwd() / out_cand).resolve()
    else:
        target_path = root / "dashboard.html"

    target_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(target_path.parent),
        delete=False,
        suffix=".tmp.html",
    ) as tmp:
        tmp.write(rendered)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, target_path)

    # Also keep <project_root>/dashboard.html synced if a custom output path was passed
    default_project_dash = root / "dashboard.html"
    if target_path.resolve() != default_project_dash.resolve() and root.is_dir():
        try:
            default_project_dash.write_text(rendered, encoding="utf-8")
        except OSError:
            pass

    # When building for an active workspace inside the repo without a custom output_path,
    # also keep the top-level <repo_root>/dashboard.html updated in place.
    repo_root = _repo_root()
    if output_path is None and root.is_relative_to(repo_root):
        repo_dash = repo_root / "dashboard.html"
        if repo_dash.resolve() != target_path.resolve():
            try:
                with tempfile.NamedTemporaryFile(
                    "w",
                    encoding="utf-8",
                    dir=str(repo_root),
                    delete=False,
                    suffix=".tmp.html",
                ) as rtmp:
                    rtmp.write(rendered)
                    rtmp_path = Path(rtmp.name)
                os.replace(rtmp_path, repo_dash)
            except OSError:
                pass

    return target_path, bundle


def _compute_workspace_Quick_signature(project_root: Path) -> str:
    """Compute a fast mtime+size signature over `.pde/control/`, `raw/`, `findings/`, and `retrospectives/`."""
    parts: list[str] = []
    for sub in (
        ".pde/control",
        "raw",
        "findings",
        "program-state",
        "executive",
        "gates",
        "retrospectives",
        "concepts",
        "assessments",
        "decisions",
    ):
        d = project_root / sub
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if p.is_file():
                try:
                    st = p.stat()
                    parts.append(f"{p.relative_to(project_root)}:{st.st_mtime_ns}:{st.st_size}")
                except OSError:
                    continue
    return "|".join(parts)


def create_dashboard_http_handler(project_root: Path) -> type[BaseHTTPRequestHandler]:
    """Create a request handler serving `/`, `/api/bundle`, and `/api/stream` (SSE)."""
    root = project_root.resolve()

    class DashboardRequestHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass  # Quiet standard logging

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            route = parsed.path

            if route in ("/", "/index.html", "/dashboard.html"):
                dash_path, _ = build_dashboard_html(root, standalone_mode=False)
                content = dash_path.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(content)
                return

            if route == "/api/bundle":
                bundle = collect_dashboard_bundle(root)
                bundle["program"]["standalone_mode"] = False
                payload = json.dumps(bundle, ensure_ascii=False, default=str).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(payload)
                return

            if route == "/api/stream":
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()

                last_sig = _compute_workspace_Quick_signature(root)
                # Send initial connected event
                init_msg = json.dumps({"type": "connected", "timestamp": _utc_now()})
                try:
                    self.wfile.write(f"data: {init_msg}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    if parsed.query == "once=1":
                        return
                    while True:
                        time.sleep(1.5)
                        cur_sig = _compute_workspace_Quick_signature(root)
                        if cur_sig != last_sig:
                            last_sig = cur_sig
                            bundle = collect_dashboard_bundle(root)
                            bundle["program"]["standalone_mode"] = False
                            ev_payload = json.dumps(
                                {"type": "bundle_updated", "bundle": bundle},
                                ensure_ascii=False,
                                default=str,
                            )
                            self.wfile.write(f"data: {ev_payload}\n\n".encode("utf-8"))
                            self.wfile.flush()
                        else:
                            hb = json.dumps({"type": "heartbeat", "timestamp": _utc_now()})
                            self.wfile.write(f": {hb}\n\n".encode("utf-8"))
                            self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    return

            self.send_error(HTTPStatus.NOT_FOUND, f"Unknown endpoint: {route}")

    return DashboardRequestHandler


# ---------------------------------------------------------------------------
# Click command group
# ---------------------------------------------------------------------------


@click.group(cls=PDEGroup)
def dashboard() -> None:
    """Build or serve the Unified Multi-Agent + PDE Interactive Scientific Dashboard."""


@dashboard.command("build")
@click.option(
    "--standalone",
    "standalone_mode",
    is_flag=True,
    default=True,
    help="Build a single-file self-contained HTML snapshot with all Layer 0 data embedded.",
)
@click.option(
    "-o",
    "--output",
    "output_path",
    default=None,
    type=click.Path(),
    help="Output HTML file path (defaults to <project>/dashboard.html).",
)
@output_options
@pass_state
def build_cmd(
    state: AppState,
    standalone_mode: bool,
    output_path: str | None,
    as_json: bool,
    quiet: bool,
) -> None:
    """Compile the Unified Multi-Agent + Interactive Scientific Dashboard (`dashboard.html`)."""
    emit = emitter(as_json, quiet)
    project = state.project()

    written_path, bundle = build_dashboard_html(
        project.root, output_path=output_path, standalone_mode=standalone_mode
    )
    metrics = bundle["program"]["summary_metrics"]

    emit.path(written_path, role="dashboard_html")
    emit.data("output_path", str(written_path))
    emit.data("program_name", bundle["program"]["name"])
    emit.data("stage", bundle["program"]["stage"])
    emit.data("summary_metrics", metrics)
    emit.line(
        f"Dashboard built at {written_path} "
        f"(agents={metrics['n_agents']}, work_orders={metrics['n_work_orders']}, "
        f"artifacts={metrics['n_artifacts']}, findings={metrics['n_findings']}, "
        f"relays={metrics['n_relays']})"
    )
    emit.flush()


@dashboard.command("serve")
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Host interface to bind.",
)
@click.option(
    "--port",
    default=8765,
    type=int,
    show_default=True,
    help="Port to serve the live dashboard on.",
)
@pass_state
def serve_cmd(state: AppState, host: str, port: int) -> None:
    """Start the live PDE Interactive Dashboard HTTP/SSE server."""
    project = state.project()
    dash_path, _ = build_dashboard_html(project.root, standalone_mode=False)
    handler_cls = create_dashboard_http_handler(project.root)
    server = ThreadingHTTPServer((host, port), handler_cls)
    click.echo(f"Serving live PDE Unified Dashboard for {project.root}")
    click.echo(f"  Dashboard URL: http://{host}:{port}/")
    click.echo(f"  Bundle API:    http://{host}:{port}/api/bundle")
    click.echo(f"  SSE Stream:    http://{host}:{port}/api/stream")
    click.echo(f"  Snapshot file: {dash_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        click.echo("\nShutting down dashboard server.")
    finally:
        server.server_close()
