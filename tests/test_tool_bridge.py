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

"""Tests for the Portable Tool Bridge (`pde_plugin/tool_bridge.py`) and MCP Server."""

from __future__ import annotations

import json
from pathlib import Path

from pde.core.env import CLI_VERSION
from pde.core.provenance import sha256_file
from pde_plugin.mcp_server import mcp
from pde_plugin.tool_bridge import (
    pde_dispatch_workorder,
    pde_exec,
    pde_render_dashboard,
    pde_validate_and_gate,
)


def test_pde_exec_doctor(tmp_path: Path) -> None:
    ws = tmp_path / "ws-doctor"
    res = pde_exec("doctor --json", project_dir=str(ws))
    assert res["ok"] is True
    assert res["exit_code"] == 0
    assert isinstance(res["data"], dict)
    assert (ws / "dashboard.html").is_file()


def test_workorder_lifecycle_correction_loop_and_lease_release(tmp_path: Path) -> None:
    ws = tmp_path / "ws-lifecycle"

    # 1. Dispatch Work Order with af3 resource lease
    dispatch = pde_dispatch_workorder(
        {
            "decision_question": "Assess target genetics for BRAF.",
            "requested_role": "computational-biologist",
            "stage": 1,
            "cycle": 1,
            "resource_class": "af3",
            "deliverables": {
                "layer_0_classes": ["pde.genetics"],
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
    busy = pde_dispatch_workorder(
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
    gate1 = pde_validate_and_gate(wo_id, run_id, project_dir=str(ws))
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
                "command": "pde genetics fetch BRAF --json",
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
    gate2 = pde_validate_and_gate(wo_id, run_id, project_dir=str(ws))
    assert gate2["ok"] is True
    assert gate2["status"] == "PASSED"
    assert gate2["ready_for_scientific_review"] is True
    assert "af3" in gate2["released_leases"]

    # 6. Render interactive dashboard
    dash = pde_render_dashboard(project_dir=str(ws))
    assert dash["ok"] is True
    assert Path(dash["output_path"]).is_file()


def test_data_integrity_failure_halts_without_retry(tmp_path: Path) -> None:
    ws = tmp_path / "ws-integrity"
    dispatch = pde_dispatch_workorder(
        {
            "decision_question": "Verify data integrity halt on mismatched source claim.",
            "requested_role": "computational-biologist",
            "deliverables": {
                "layer_0_classes": ["pde.genetics"],
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

    gate = pde_validate_and_gate(wo_id, run_id, project_dir=str(ws))
    assert gate["ok"] is False
    assert gate["status"] == "DATA_INTEGRITY_FAILURE"
    assert gate["retry_allowed"] is False
    assert "source_tags_resolve" in gate["checks_failed"]


def test_mcp_server_exposes_all_4_tools() -> None:
    assert mcp.name == "pde-engine"
