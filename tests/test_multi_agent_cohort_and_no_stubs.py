"""Verification tests for module surface integrity, dynamic workspace isolation,
Check 7 version policy enforcement, Stage 0-4 manufacturing assessments, and
multi-persona cohort orchestration.
"""

from __future__ import annotations

import json
from pathlib import Path

from pkde_plugin.tool_bridge import (
    pkde_bootstrap_session,
    pkde_dispatch_cohort,
    pkde_exec,
    pkde_manage_cohort,
    pkde_render_dashboard,
    pkde_validate_and_gate,
    resolve_project_root,
)
from tools.pkde.commands.validate import _check_version_policy
from tools.pkde.core.manufacturing import STAGE_REQUIREMENTS, assess_stage

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_module_surface_and_stage_coverage() -> None:
    """Verify tool bridge imports and Stage 0-4 manufacturing support definitions."""
    tb_src = (REPO_ROOT / "pkde_plugin" / "tool_bridge.py").read_text(encoding="utf-8")
    assert "def build_dashboard_html(" not in tb_src
    assert "def ensure_dashboard_server(" not in tb_src

    val_src = (REPO_ROOT / "tools" / "pkde" / "commands" / "validate.py").read_text(encoding="utf-8")
    assert "placeholder" not in val_src.lower()

    mfg_core_src = (REPO_ROOT / "tools" / "pkde" / "core" / "manufacturing.py").read_text(encoding="utf-8")
    assert "placeholder" not in mfg_core_src.lower()
    for stage_num in (0, 2, 3, 4):
        assert STAGE_REQUIREMENTS[stage_num]["status"] == "supported"

    mfg_cmd_src = (REPO_ROOT / "tools" / "pkde" / "commands" / "manufacturing.py").read_text(encoding="utf-8")
    assert "placeholder" not in mfg_cmd_src.lower()


def test_compiled_agents_have_subagent_and_communication_tools() -> None:
    """Verify all 22 compiled agent definitions have subagent & communication tools."""
    agents_dir = REPO_ROOT / ".agents" / "plugins" / "pharmakon-discovery-engine" / "agents"
    agent_files = sorted(agents_dir.glob("pkde-*.md"))
    assert len(agent_files) == 22

    orchestrators = {
        "pkde-science-program-lead.md",
        "pkde-research-operations-controller.md",
        "pkde-hypex-supervisor.md",
    }
    for md_file in agent_files:
        text = md_file.read_text(encoding="utf-8")
        assert "- send_message" in text, f"{md_file.name} missing send_message"
        assert "- multi_replace_file_content" in text, f"{md_file.name} missing multi_replace_file_content"
        if md_file.name in orchestrators:
            assert "mainAgent: true" in text, f"{md_file.name} missing mainAgent: true"
            assert "- invoke_subagent" in text, f"{md_file.name} missing invoke_subagent"
            assert "- manage_subagents" in text, f"{md_file.name} missing manage_subagents"


def test_dynamic_workspace_isolation_and_fresh_bootstrap(tmp_path: Path, monkeypatch) -> None:
    """Verify resolve_project_root never falls back to static demo .pkde-workspace root
    and fresh=True wipes stale workspace state cleanly.
    """
    monkeypatch.delenv("PKDE_PROJECT", raising=False)
    monkeypatch.chdir(tmp_path)
    resolved = resolve_project_root(None)
    assert resolved != (REPO_ROOT / ".pkde-workspace").resolve()

    ws = tmp_path / "clean-ws"
    res1 = pkde_bootstrap_session(
        prompt="Initial prompt",
        project_dir=str(ws),
        program_name="Prog-A",
        stage=1,
        start_server=False,
    )
    assert res1["ok"] is True
    (ws / "raw" / "chemistry").mkdir(parents=True, exist_ok=True)
    (ws / "raw" / "chemistry" / "stale.json").write_text("{}", encoding="utf-8")
    (ws / "findings" / "chemistry").mkdir(parents=True, exist_ok=True)
    (ws / "findings" / "chemistry" / "stale.md").write_text("# Stale", encoding="utf-8")

    # Re-bootstrap with fresh=True
    res2 = pkde_bootstrap_session(
        prompt="Fresh prompt",
        project_dir=str(ws),
        program_name="Prog-B",
        stage=2,
        start_server=False,
        fresh=True,
    )
    assert res2["ok"] is True
    assert not (ws / "raw" / "chemistry" / "stale.json").exists()
    assert not (ws / "findings" / "chemistry" / "stale.md").exists()


def test_check_version_policy_real_verification(tmp_path: Path, monkeypatch) -> None:
    """Verify Check 7 (_check_version_policy) validates program.yaml policies and sidecars."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "raw" / "chemistry").mkdir(parents=True, exist_ok=True)
    raw_file = tmp_path / "raw" / "chemistry" / "cmpd.json"
    raw_file.write_text('{"name": "cmpd"}', encoding="utf-8")
    meta_file = tmp_path / "raw" / "chemistry" / "cmpd.json.meta.json"
    meta_file.write_text(
        json.dumps(
            {
                "cli_version": "0.1.0",
                "env_version": "pkde-tools-2026.03",
                "tool": "compound",
                "subcommand": "profile",
            }
        ),
        encoding="utf-8",
    )

    # 1. Matching policy passes
    (tmp_path / "program.yaml").write_text(
        "version_policy:\n  required_cli_version: '0.1.0'\n  required_env_version: 'pkde-tools-2026.03'\n",
        encoding="utf-8",
    )
    res_ok = _check_version_policy(tmp_path, ["raw/chemistry/cmpd.json"], wo_id="WO-001")
    assert res_ok["passed"] is True

    # 2. Mismatched required_cli_version fails
    (tmp_path / "program.yaml").write_text(
        "version_policy:\n  required_cli_version: '9.9.9'\n",
        encoding="utf-8",
    )
    res_fail = _check_version_policy(tmp_path, ["raw/chemistry/cmpd.json"], wo_id="WO-001")
    assert res_fail["passed"] is False
    assert any("9.9.9" in issue for issue in res_fail["issues"])


def test_manufacturing_assess_stages_0_2_3_4(tmp_path: Path) -> None:
    """Verify Stage 0, 2, 3, and 4 manufacturing assessments and CLI execution."""
    concept = {
        "id": "IC-001",
        "revision": 1,
        "modality": "small_molecule",
        "entity_ref": "COCCOc1cc2ncnc(Nc3cccc(C#C)c3)c2cc1OCCOC",
        "delivery_assumptions": {"route": "oral"},
    }
    s0 = assess_stage(concept, stage=0, sa_score_data={"sa_score": 2.8})
    assert s0["evidence_status"] == "supported"
    assert s0["manufacturing_stage"] == 0

    s2 = assess_stage(
        concept,
        stage=2,
        sa_score_data={"sa_score": 3.1},
        retro_data={"routes": [{"steps": 4}], "shortest_route_steps": 4, "feasible": True},
    )
    assert s2["evidence_status"] == "supported"
    assert s2["manufacturing_stage"] == 2

    s3 = assess_stage(
        concept,
        stage=3,
        process_data={"feasible": True, "batch_scale_g": 25.0, "overall_yield_pct": 62.0, "purity_pct": 98.8},
    )
    assert s3["evidence_status"] == "supported"
    assert s3["manufacturing_stage"] == 3

    s4_missing = assess_stage(concept, stage=4)
    assert s4_missing["evidence_status"] == "insufficient_evidence"

    s4_ok = assess_stage(
        concept,
        stage=4,
        supply_data={"gmp_ready": True, "batch_scale_kg": 5.0, "qualified_vendors": 2},
    )
    assert s4_ok["evidence_status"] == "supported"
    assert s4_ok["manufacturing_stage"] == 4

    # Also test CLI execution: pkde manufacturing assess <concept_path> --stage 2
    ws = tmp_path / "mfg-ws"
    pkde_bootstrap_session(
        prompt="Assess Stage 2 manufacturing",
        project_dir=str(ws),
        program_name="MfgTest",
        start_server=False,
    )
    concept_file = ws / "concept.json"
    concept_file.write_text(json.dumps(concept), encoding="utf-8")
    p1 = pkde_exec(
        ["manufacturing", "assess", str(concept_file), "--stage", "2"],
        project_dir=str(ws),
    )
    assert p1["ok"] is True, p1
    assert (ws / "raw" / "manufacturing" / "IC-001.manufacturing-stage2.json").exists()


def test_multi_persona_cohort_dispatch_waves_and_attribution(tmp_path: Path) -> None:
    """Verify multi-persona cohort dispatch, wave scheduling, subagent binding,
    concurrent work-order attribution, and automatic Wave 2 promotion.
    """
    ws = tmp_path / "cohort-ws"
    pkde_bootstrap_session(
        prompt="Multi-persona cohort verification",
        project_dir=str(ws),
        program_name="CohortProgram",
        stage=1,
        start_server=False,
    )

    specs = [
        {
            "spec_id": "chem",
            "role": "medicinal-chemist",
            "stage": "Stage 1",
            "cycle": 1,
            "decision_question": "Profile erlotinib physicochemical properties",
            "deliverables": {
                "layer_0_classes": ["compounds"],
                "layer_1": ["findings/chemistry/erlotinib-props.md"],
            },
        },
        {
            "spec_id": "dmpk",
            "role": "admet-dmpk-scientist",
            "stage": "Stage 1",
            "cycle": 1,
            "decision_question": "Predict erlotinib ADMET endpoints",
            "deliverables": {
                "layer_0_classes": ["admet"],
                "layer_1": ["findings/dmpk/erlotinib-admet.md"],
            },
        },
        {
            "spec_id": "tox",
            "role": "preclinical-toxicologist",
            "stage": "Stage 1",
            "cycle": 1,
            "depends_on": ["chem", "dmpk"],
            "decision_question": "Evaluate preclinical genotoxicity battery after chem and dmpk",
            "deliverables": {
                "layer_0_classes": ["tox"],
                "layer_1": ["findings/tox/erlotinib-genotox.md"],
            },
        },
    ]

    cohort = pkde_dispatch_cohort(specs=specs, project_dir=str(ws))
    assert cohort["ok"] is True
    assert cohort["cohort_size"] == 3
    assert set(cohort["wave_1_started"]) == {"WO-001", "WO-002"}
    assert cohort["wave_2_plus_queued"] == ["WO-003"]
    assert len(cohort["subagent_invocations"]) == 2

    # Bind subagent conversation IDs for Wave 1 WOs
    b1 = pkde_manage_cohort(
        action="bind_subagent",
        work_order_id="WO-001",
        subagent_id="conv-medchem-001",
        project_dir=str(ws),
    )
    b2 = pkde_manage_cohort(
        action="bind_subagent",
        work_order_id="WO-002",
        subagent_id="conv-dmpk-002",
        project_dir=str(ws),
    )
    assert b1["ok"] is True
    assert b2["ok"] is True

    # Execute Wave 1 tools with explicit work_order_id + agent_role attribution
    smiles = "COCCOc1cc2ncnc(Nc3cccc(C#C)c3)c2cc1OCCOC"
    for cmd in (
        ["compound", "profile", smiles, "--name", "erlotinib_props"],
        ["compound", "analyze", "erlotinib_props"],
    ):
        res = pkde_exec(
            cmd,
            project_dir=str(ws),
            work_order_id="WO-001",
            agent_role="medicinal-chemist",
            agent_slug="pkde-medicinal-chemist",
            run_id="RUN-001",
        )
        assert res["ok"] is True

    for cmd in (
        ["admet", "predict", smiles, "--name", "erlotinib_admet"],
        ["admet", "analyze", "erlotinib_admet"],
    ):
        res = pkde_exec(
            cmd,
            project_dir=str(ws),
            work_order_id="WO-002",
            agent_role="admet-dmpk-scientist",
            agent_slug="pkde-admet-dmpk-scientist",
            run_id="RUN-002",
        )
        assert res["ok"] is True

    # Verify .meta.json sidecars carry exact work_order_id and written_by attribution
    chem_meta = json.loads((ws / "raw" / "compounds" / "erlotinib_props.descriptors.meta.json").read_text(encoding="utf-8"))
    dmpk_meta = json.loads((ws / "raw" / "admet" / "erlotinib_admet.predict.meta.json").read_text(encoding="utf-8"))
    assert chem_meta["work_order_id"] == "WO-001"
    assert chem_meta["written_by"] == "pkde-medicinal-chemist"
    assert dmpk_meta["work_order_id"] == "WO-002"
    assert dmpk_meta["written_by"] == "pkde-admet-dmpk-scientist"

    # Write compliant Layer 1 findings for WO-001 and WO-002
    chem_analysis = json.loads((ws / "raw" / "compounds" / "erlotinib_props.analysis.json").read_text(encoding="utf-8"))
    chem_verdict = chem_analysis["assessment"]["verdict"]
    chem_relays = "\n".join(f"- **Relay: `{r['code']}`** -- {r.get('message') or r.get('detail') or 'Addressed.'}" for r in chem_analysis.get("mandatory_relays", [])) or "- None"
    (ws / "findings" / "chemistry").mkdir(parents=True, exist_ok=True)
    (ws / "findings" / "chemistry" / "erlotinib-props.md").write_text(
        f"""# Erlotinib Physicochemical Profile (WO-001-r1)

## Summary
Erlotinib molecular weight is 393.44 Da {{source: raw/compounds/erlotinib_props.descriptors.json $.descriptors.molecular_weight}} with verdict `{chem_verdict}` {{source: raw/compounds/erlotinib_props.analysis.json $.assessment.verdict}}.

## Key Findings
{chem_relays}

## Verdict
{chem_verdict.upper()}

## Evidence
- [Descriptors](../../raw/compounds/erlotinib_props.descriptors.json)
- [Analysis](../../raw/compounds/erlotinib_props.analysis.json)

## Implications
Proceed to downstream safety evaluation.
""",
        encoding="utf-8",
    )

    dmpk_analysis = json.loads((ws / "raw" / "admet" / "erlotinib_admet.analysis.json").read_text(encoding="utf-8"))
    dmpk_verdict = dmpk_analysis["assessment"]["verdict"]
    dmpk_relays = "\n".join(f"- **Relay: `{r['code']}`** -- {r.get('message') or r.get('detail') or 'Addressed.'}" for r in dmpk_analysis.get("mandatory_relays", [])) or "- None"
    (ws / "findings" / "dmpk").mkdir(parents=True, exist_ok=True)
    (ws / "findings" / "dmpk" / "erlotinib-admet.md").write_text(
        f"""# Erlotinib ADMET Profile (WO-002-r1)

## Summary
Erlotinib ADMET analysis completed with verdict `{dmpk_verdict}` {{source: raw/admet/erlotinib_admet.analysis.json $.assessment.verdict}} and MW 393.44 Da {{source: raw/admet/erlotinib_admet.predict.json $.molecular_descriptors.mw}}.

## Key Findings
{dmpk_relays}

## Verdict
{dmpk_verdict.upper()}

## Evidence
- [ADMET Predict](../../raw/admet/erlotinib_admet.predict.json)
- [ADMET Analysis](../../raw/admet/erlotinib_admet.analysis.json)

## Implications
Proceed to downstream safety evaluation.
""",
        encoding="utf-8",
    )

    # Validate Wave 1 cohort and verify Wave 2 (WO-003) is automatically promoted to running!
    gate_res = pkde_validate_and_gate("all", project_dir=str(ws))
    assert gate_res["ok"] is True, gate_res
    assert gate_res["validated_count"] == 2
    assert len(gate_res["unblocked_work_orders"]) == 1
    assert gate_res["unblocked_work_orders"][0]["work_order_id"] == "WO-003"

    # Render standalone dashboard and confirm subagent_id and cross-WO dependency edges exist
    dash = pkde_render_dashboard(project_dir=str(ws))
    assert dash["ok"] is True
    html = (ws / "dashboard.html").read_text(encoding="utf-8")
    assert "conv-medchem-001" in html
    assert "conv-dmpk-002" in html
    assert "depends-on WO-001" in html
    assert "depends-on WO-002" in html
