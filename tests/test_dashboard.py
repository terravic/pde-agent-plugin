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

"""Tests for the Unified Multi-Agent + PDE Interactive Scientific Dashboard (`pde dashboard`)."""

from __future__ import annotations

from pathlib import Path

from pde.commands.dashboard import (
    ALL_10_CHECKS,
    _classify_viewer,
    _detect_domain_studio,
    _load_roles_catalog,
    build_dashboard_html,
    collect_dashboard_bundle,
)
from pde.core.context import init_project
from tests._fixture_workspace import populate_demo_workspace


def test_dashboard_created_on_init_and_incremental_population(tmp_path: Path) -> None:
    ws = tmp_path / "live-program"
    init_project(ws)
    dash_file = ws / "dashboard.html"
    assert dash_file.is_file(), "dashboard.html should be created immediately upon init_project"
    initial_html = dash_file.read_text(encoding="utf-8")
    assert "window.__PDE_BUNDLE__" in initial_html


def test_viewer_classification_covers_all_14_types() -> None:
    samples = {
        "KRAS_G12D.afdb.json": "plddt",
        "KRAS_G12D.pae.json": "pae",
        "KRAS.gnomad-constraint.json": "constraint",
        "KRAS.tissue.json": "expression",
        "kras_resistance.tournament.json": "tournament",
        "KRAS_G12D_SIIP.pockets.json": "pockets",
        "MRTX1133.predict.json": "admet",
        "MRTX1133_SIIP.docking_result.json": "docking_scores",
        "MRTX1133_SIIP.contacts.json": "contacts",
        "MRTX1133.3d.sdf": "sdf_3d",
        "KRAS_G12D.cif": "structure_3d",
        "MRTX1133_SIIP.poses.pdbqt": "docking_3d",
        "MRTX1133_series.brics.json": "brics",
        "KRAS_G12D_panel.json": "json",
    }
    seen_types = set()
    for filename, expected_vtype in samples.items():
        vtype, _ = _classify_viewer(filename)
        assert vtype == expected_vtype, f"Expected {expected_vtype} for {filename}, got {vtype}"
        seen_types.add(vtype)
    assert len(seen_types) >= 13


def test_detect_domain_studio_covers_all_specialist_domains() -> None:
    assert _detect_domain_studio("KRAS_G12D_panel.json", "pde.bioactivity", {}, {}) == ("bioactivity_studio", "Bioactivity, Dose-Response & Selectivity Studio")
    assert _detect_domain_studio("rat_iv_po.pk.json", "pde.pk", {}, {}) == ("pk_studio", "PK / NCA / Scaling & DDI Studio")
    assert _detect_domain_studio("repeat_dose_14d.json", "pde.tox", {}, {}) == ("tox_studio", "Preclinical Toxicology & Safety Studio")
    assert _detect_domain_studio("MRTX1133.descriptors.json", "pde.descriptors", {}, {}) == ("medchem_studio", "MedChem Descriptors, Alerts & SAR Studio")
    assert _detect_domain_studio("rs12345.alphagenome.json", "pde.genomics", {}, {}) == ("omics_studio", "Genomics, Variant Effect & Transcriptomics Studio")
    assert _detect_domain_studio("kras.trials.json", "pde.pipeline", {}, {}) == ("competitive_studio", "Clinical Pipeline, Patent & Manufacturing Studio")


def test_roles_catalog_loads_all_22_roles() -> None:
    catalog = _load_roles_catalog()
    assert len(catalog) == 22
    for role, info in catalog.items():
        assert info["role"] == role
        assert isinstance(info["skills"], list)
        assert len(info["skills"]) >= 1, f"Role {role} should have at least 1 skill"


def test_dashboard_bundle_and_standalone_html(tmp_path: Path) -> None:
    ws = tmp_path / "kras-program"
    populate_demo_workspace(ws)

    bundle = collect_dashboard_bundle(ws)
    assert bundle["program"]["name"] == "KRAS-G12D-Selective-Inhibitor"
    metrics = bundle["program"]["summary_metrics"]
    assert metrics["n_work_orders"] == 5
    assert metrics["n_runs"] == 5
    assert metrics["n_validated"] == 5
    assert metrics["validation_pass_rate"] == 100.0
    assert metrics["n_artifacts"] >= 14
    assert metrics["n_findings"] == 5
    assert metrics["n_relays"] >= 5
    assert metrics["n_relays_addressed"] == metrics["n_relays"]
    assert metrics["n_concepts"] == 1
    assert metrics["n_assessments"] == 1
    assert metrics["n_decisions"] == 1
    assert metrics["n_retrospectives"] == 1

    # Verify multi-agent graph nodes, edges, context snapshots, retrospectives, and environment
    agent_sys = bundle["agent_system"]
    nodes = agent_sys["nodes"]
    edges = agent_sys["edges"]
    assert len(nodes) >= 7  # orchestrator + controller + 5 dispatched specialists
    assert len(edges) >= 5
    assert len(agent_sys["contexts"]) == 5
    assert len(agent_sys["retrospectives"]) == 1
    assert "cli_binaries" in agent_sys["environment"]
    assert "python_libraries" in agent_sys["environment"]

    # Verify every WO node (5 specialists + 5 validator child nodes) has 10-check validation matrix and injected skills
    wo_nodes = [n for n in nodes if n.get("work_order_id")]
    assert len(wo_nodes) == 10
    for wn in wo_nodes:
        assert len(wn["injected_skills"]) >= 1
        assert len(wn["validation"]["checks"]) == len(ALL_10_CHECKS)

    # Verify WO-003 specialist node records its 1-cycle mechanical correction loop and context snapshot
    wo3_spec = next(n for n in wo_nodes if n["work_order_id"] == "WO-003" and n["category"] == "Specialist")
    assert wo3_spec["correction_cycle"] == 1
    assert wo3_spec["context_snapshot"] is not None
    assert len(wo3_spec["context_snapshot"]["hash"]) == 64

    # Verify KRAS_G12D_panel.json is routed to bioactivity_studio while keeping viewer_type == 'json'
    bio_art = next(a for a in bundle["science"]["artifacts"] if a["name"] == "KRAS_G12D_panel.json")
    assert bio_art["viewer_type"] == "json"
    assert bio_art["domain_studio"] == "bioactivity_studio"

    # Verify Stage 0-3 concepts, assessments, and decisions are collected
    tg = bundle["science"]["triage_and_gates"]
    assert len(tg["concepts"]) == 1 and tg["concepts"][0]["id"] == "IC-001"
    assert len(tg["assessments"]) == 1 and tg["assessments"][0]["id"] == "AR-001"
    assert len(tg["decisions"]) == 1 and tg["decisions"][0]["id"] == "DR-001"

    # Verify default dashboard.html was written and updated in the workspace
    out_html = ws / "dashboard.html"
    out_path, _ = build_dashboard_html(ws, standalone_mode=True)
    assert out_html.is_file()
    html_text = out_html.read_text(encoding="utf-8")
    assert "window.__PDE_BUNDLE__" in html_text
    assert "KRAS-G12D-Selective-Inhibitor" in html_text
    assert "buildLineageForest" in html_text
    assert "renderPlotWithFallback" in html_text
    assert "renderSvgChartFallback" in html_text
    assert "canUseWebGL" in html_text
    assert "renderCanvas3DMoleculeFallback" in html_text
    assert "renderEmbeddedBioactivityStudio" in html_text
    assert "renderEmbeddedPkStudio" in html_text
    assert "renderEmbeddedToxStudio" in html_text
    assert "renderEmbeddedMedChemStudio" in html_text
    assert "renderEmbeddedOmicsStudio" in html_text
    assert "renderEmbeddedCompetitiveStudio" in html_text
    assert "renderRetrosAndEnv" in html_text
    assert agent_sys["environment"]["bootstrap_ready"] is True
    assert out_path == out_html

