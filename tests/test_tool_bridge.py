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

"""Tests for the Portable Tool Bridge (`pkde_plugin/tool_bridge.py`) and MCP Server."""

from __future__ import annotations

import json
from pathlib import Path

from pkde.core.env import CLI_VERSION
from pkde.core.provenance import sha256_file
from pkde_plugin.mcp_server import mcp
from pkde_plugin.tool_bridge import (
    pkde_dispatch_workorder,
    pkde_exec,
    pkde_render_dashboard,
    pkde_validate_and_gate,
)


def test_pkde_exec_doctor(tmp_path: Path) -> None:
    ws = tmp_path / "ws-doctor"
    res = pkde_exec("doctor --json", project_dir=str(ws))
    assert res["ok"] is True
    assert res["exit_code"] == 0
    assert isinstance(res["data"], dict)
    assert (ws / "dashboard.html").is_file()


def test_workorder_lifecycle_correction_loop_and_lease_release(tmp_path: Path) -> None:
    ws = tmp_path / "ws-lifecycle"

    # 1. Dispatch Work Order with af3 resource lease
    dispatch = pkde_dispatch_workorder(
        {
            "decision_question": "Assess target genetics for BRAF.",
            "requested_role": "computational-biologist",
            "stage": 1,
            "cycle": 1,
            "resource_class": "af3",
            "deliverables": {
                "layer_0_classes": ["pkde.genetics"],
                "layer_1": ["findings/computational-biology/braf-genetics.md"],
            },
        },
        project_dir=str(ws),
    )
    assert dispatch["ok"] is True
    assert dispatch["status"] == "DISPATCHED"
    wo_id = dispatch["work_order_id"]
    run_id = dispatch["run_id"]
    assert Path(dispatch["context_snapshot_path"]).is_file()
    assert Path(dispatch["lease_path"]).is_file()

    # 2. Verify second dispatch requesting the same 'af3' lease is blocked with RESOURCE_BUSY
    busy = pkde_dispatch_workorder(
        {
            "decision_question": "Concurrent AF3 job should be blocked while lease is held.",
            "requested_role": "structural-biologist",
            "resource_class": "af3",
        },
        project_dir=str(ws),
    )
    assert busy["ok"] is False
    assert busy["status"] == "RESOURCE_BUSY"

    # 3. Validate before deliverables exist -> triggers Cycle 1 CORRECTION_REQUIRED
    gate1 = pkde_validate_and_gate(wo_id, run_id, project_dir=str(ws))
    assert gate1["ok"] is False
    assert gate1["status"] == "CORRECTION_REQUIRED"
    assert gate1["retry_allowed"] is True
    assert gate1["correction_cycle"] == 1
    assert "deliverables_exist" in gate1["checks_failed"]
    assert f"CORRECTION REQUIRED {wo_id}" in gate1["correction_prompt"]

    # 4. Write valid Layer 0 artifact (.json + .meta.json + .analysis.json) and Layer 1 report
    raw_file = ws / "raw/genomics/BRAF.gnomad-constraint.json"
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    raw_file.write_text(
        json.dumps({"gene": "BRAF", "constraint": {"pLI": 0.99}}, indent=2) + "\n",
        encoding="utf-8",
    )
    digest = sha256_file(raw_file)

    (ws / "raw/genomics/BRAF.gnomad-constraint.json.meta.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "record_type": "provenance",
                "command": "pkde genetics fetch BRAF --json",
                "cli_version": CLI_VERSION,
                "work_order_id": wo_id,
                "outputs": [
                    {
                        "path": "raw/genomics/BRAF.gnomad-constraint.json",
                        "sha256": digest,
                    }
                ],
                "mandatory_relays": [
                    {"code": "BRAF_PLI_HIGH", "detail": "Monitor WT BRAF."}
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (ws / "raw/genomics/BRAF.gnomad-constraint.json.analysis.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "record_type": "analysis",
                "source": "raw/genomics/BRAF.gnomad-constraint.json",
                "threshold_set": "genetics-v1",
                "work_order_id": wo_id,
                "verdict": "pass",
                "summary": "BRAF pLI is 0.99.",
                "mandatory_relays": [
                    {"code": "BRAF_PLI_HIGH", "detail": "Monitor WT BRAF."}
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    finding_file = ws / "findings/computational-biology/braf-genetics.md"
    finding_file.parent.mkdir(parents=True, exist_ok=True)
    finding_file.write_text(
        f"# BRAF Genetics ({wo_id}-r1)\n\n"
        "## Summary\n"
        "BRAF has pLI of 0.99 {source: raw/genomics/BRAF.gnomad-constraint.json $.constraint.pLI}.\n\n"
        "## Key Findings\n"
        "- **Relay: `BRAF_PLI_HIGH`** — Addressed.\n\n"
        "## Verdict\nPASS\n\n"
        "## Evidence\n- [BRAF JSON](../../raw/genomics/BRAF.gnomad-constraint.json)\n\n"
        "## Implications\nProceed.\n",
        encoding="utf-8",
    )

    # 5. Re-run validation -> PASSED and releases af3 lease
    gate2 = pkde_validate_and_gate(wo_id, run_id, project_dir=str(ws))
    assert gate2["ok"] is True
    assert gate2["status"] == "PASSED"
    assert gate2["ready_for_scientific_review"] is True
    assert "af3" in gate2["released_leases"]

    # 6. Render interactive dashboard
    dash = pkde_render_dashboard(project_dir=str(ws))
    assert dash["ok"] is True
    assert Path(dash["output_path"]).is_file()


def test_data_integrity_failure_halts_without_retry(tmp_path: Path) -> None:
    ws = tmp_path / "ws-integrity"
    dispatch = pkde_dispatch_workorder(
        {
            "decision_question": "Verify data integrity halt on mismatched source claim.",
            "requested_role": "computational-biologist",
            "deliverables": {
                "layer_0_classes": ["pkde.genetics"],
                "layer_1": ["findings/computational-biology/bad-claim.md"],
            },
        },
        project_dir=str(ws),
    )
    wo_id = dispatch["work_order_id"]
    run_id = dispatch["run_id"]

    raw_file = ws / "raw/genomics/TP53.gnomad-constraint.json"
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    raw_file.write_text(
        json.dumps({"gene": "TP53", "constraint": {"pLI": 0.95}}, indent=2) + "\n",
        encoding="utf-8",
    )
    digest = sha256_file(raw_file)
    (ws / "raw/genomics/TP53.gnomad-constraint.json.meta.json").write_text(
        json.dumps(
            {
                "record_type": "provenance",
                "cli_version": CLI_VERSION,
                "work_order_id": wo_id,
                "outputs": [
                    {
                        "path": "raw/genomics/TP53.gnomad-constraint.json",
                        "sha256": digest,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (ws / "raw/genomics/TP53.gnomad-constraint.json.analysis.json").write_text(
        json.dumps(
            {
                "record_type": "analysis",
                "source": "raw/genomics/TP53.gnomad-constraint.json",
                "threshold_set": "genetics-v1",
                "work_order_id": wo_id,
            }
        ),
        encoding="utf-8",
    )

    # Claim pLI is 0.12 when actual JSON has 0.95 -> triggers source_tags_resolve DATA_INTEGRITY failure
    finding = ws / "findings/computational-biology/bad-claim.md"
    finding.parent.mkdir(parents=True, exist_ok=True)
    finding.write_text(
        f"# TP53 ({wo_id}-r1)\n\n"
        "## Summary\n"
        "Claimed pLI is 0.12 {source: raw/genomics/TP53.gnomad-constraint.json $.constraint.pLI}.\n\n"
        "## Key Findings\n- Mismatched number.\n\n"
        "## Implications\nHalt.\n",
        encoding="utf-8",
    )

    gate = pkde_validate_and_gate(wo_id, run_id, project_dir=str(ws))
    assert gate["ok"] is False
    assert gate["status"] == "DATA_INTEGRITY_FAILURE"
    assert gate["retry_allowed"] is False
    assert "source_tags_resolve" in gate["checks_failed"]


async def test_mcp_server_exposes_all_6_tools_with_complete_boolean_annotations() -> None:
    assert mcp.name == "pkde-engine"
    tools = await mcp.list_tools()
    by_name = {t.name: t for t in tools}

    expected_hints = {
        "pkde_bootstrap_session": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        "pkde_exec": {
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
        "pkde_dispatch_workorder": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        "pkde_log_agent_message": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        "pkde_validate_and_gate": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        "pkde_render_dashboard": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    }

    assert set(by_name.keys()) == set(expected_hints.keys())

    for tool_name, expected in expected_hints.items():
        tool = by_name[tool_name]
        assert tool.annotations is not None, f"{tool_name} is missing ToolAnnotations"
        dumped = tool.annotations.model_dump(by_alias=True, exclude_none=True)
        for hint_key, expected_val in expected.items():
            assert hint_key in dumped, f"{tool_name} missing {hint_key}"
            assert isinstance(dumped[hint_key], bool), f"{tool_name}.{hint_key} must be bool"
            assert dumped[hint_key] is expected_val, (
                f"{tool_name}.{hint_key} expected {expected_val}, got {dumped[hint_key]}"
            )


def test_cli_workorder_dispatch_and_validate_gate(tmp_path: Path) -> None:
    """Verify workorder dispatch and validate-and-gate execute natively via ./bin/pkde CLI."""
    ws = tmp_path / "ws-cli-dispatch"
    spec_json = json.dumps(
        {
            "decision_question": "Assess target genetics for BRAF via CLI dispatch.",
            "requested_role": "computational-biologist",
            "stage": 1,
            "cycle": 1,
            "deliverables": {
                "layer_0_classes": ["pkde.genetics"],
                "layer_1": ["findings/computational-biology/braf.md"],
            },
        }
    )
    res_dispatch = pkde_exec(
        f"workorder dispatch --spec {json.dumps(spec_json)} --json",
        project_dir=str(ws),
        auto_refresh_dashboard=False,
    )
    assert res_dispatch["ok"] is True
    data = res_dispatch["data"]
    assert isinstance(data, dict)
    assert data["status"] == "DISPATCHED"
    wo_id = data["work_order_id"]
    run_id = data["run_id"]

    res_gate = pkde_exec(
        f"workorder validate-and-gate {wo_id} --run-id {run_id} --json",
        project_dir=str(ws),
        auto_refresh_dashboard=False,
    )
    gate_data = res_gate["data"]
    assert isinstance(gate_data, dict)
    assert gate_data["status"] == "CORRECTION_REQUIRED"
    assert gate_data["work_order_id"] == wo_id


def test_hermetic_pythonpath_isolation(tmp_path: Path) -> None:
    """Verify bin/env.sh, bin/pkde, and _build_env isolate from incompatible host PYTHONPATH."""
    import os
    import subprocess
    from unittest.mock import patch
    from pkde_plugin.tool_bridge import REPO_ROOT, _build_env

    poison_dir = tmp_path / "poison_site_packages"
    poison_numpy = poison_dir / "numpy"
    poison_numpy.mkdir(parents=True, exist_ok=True)
    (poison_numpy / "__init__.py").write_text(
        "raise ModuleNotFoundError(\"No module named 'numpy._core._multiarray_umath'\")\n",
        encoding="utf-8",
    )

    with patch.dict(os.environ, {"PYTHONPATH": str(poison_dir), "PKDE_OFFLINE": "1"}):
        built_env = _build_env(tmp_path / "ws")
        assert str(poison_dir) not in built_env["PYTHONPATH"].split(os.pathsep)

        proc = subprocess.run(
            [str(REPO_ROOT / "bin" / "pkde"), "doctor", "--json"],
            cwd=str(REPO_ROOT),
            env={**os.environ, "PYTHONPATH": str(poison_dir), "PKDE_OFFLINE": "1"},
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert proc.returncode == 0, f"Doctor failed under poisoned PYTHONPATH: {proc.stderr}"
        payload = json.loads(proc.stdout)
        assert payload["ok"] is True


def test_doctor_offline_degraded_mode(tmp_path: Path) -> None:
    """Verify pkde doctor reports execution_mode='degraded_offline' when outbound network is unavailable."""
    import os
    import subprocess
    from pkde_plugin.tool_bridge import REPO_ROOT

    env = {
        **os.environ,
        "PKDE_OFFLINE": "1",
        "PKDE_PROJECT": str(tmp_path / "ws-offline"),
    }
    subprocess.run(
        [str(REPO_ROOT / "bin" / "pkde"), "init", str(tmp_path / "ws-offline")],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    proc_json = subprocess.run(
        [str(REPO_ROOT / "bin" / "pkde"), "doctor", "--json"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc_json.returncode == 0
    doc = json.loads(proc_json.stdout)
    assert doc["execution_mode"] == "degraded_offline"
    assert doc["network_reachable"] is False

    proc_txt = subprocess.run(
        [str(REPO_ROOT / "bin" / "pkde"), "doctor"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc_txt.returncode == 0
    assert "DEGRADED (LOCAL-ONLY SANDBOX)" in proc_txt.stdout
    assert "ENVIRONMENT_BLOCKED" in proc_txt.stdout


