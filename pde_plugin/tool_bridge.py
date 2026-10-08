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

"""Portable Tool Bridge for the Pharmakon Discovery Engine MCP Server and Agent Harness.

Provides the 4 core orchestration and execution primitives:
1. ``pde_exec`` — Execute any two-phase or control-plane ``pde`` CLI command.
2. ``pde_dispatch_workorder`` — Atomic 4-step Work Order intake, snapshot, lease, and run start.
3. ``pde_validate_and_gate`` — 10-check mechanical validation gate and correction loop driver.
4. ``pde_render_dashboard`` — Build the self-contained multi-agent and scientific dashboard HTML.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
VENDOR_HYPEX_DIR = TOOLS_DIR / "vendor" / "hypex"

for _p in (str(REPO_ROOT), str(TOOLS_DIR), str(VENDOR_HYPEX_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pde.commands.dashboard import build_dashboard_html  # noqa: E402
from pde.core import controlstore  # noqa: E402
from pde.core.context import init_project  # noqa: E402


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _has_raw_artifacts(workspace: Path) -> bool:
    raw_dir = workspace / "raw"
    return (workspace / ".pde").is_dir() and raw_dir.is_dir() and any(raw_dir.rglob("*.meta.json"))


def resolve_project_root(project_dir: str | Path | None = None) -> Path:
    """Resolve and initialize the active PDE project workspace root."""
    if project_dir:
        root = Path(project_dir).expanduser().resolve()
    elif os.environ.get("PDE_PROJECT"):
        root = Path(os.environ["PDE_PROJECT"]).expanduser().resolve()
    else:
        default_prog = (REPO_ROOT / ".pde-workspace" / "default-program").resolve()
        parent_ws = (REPO_ROOT / ".pde-workspace").resolve()
        if not _has_raw_artifacts(default_prog) and _has_raw_artifacts(parent_ws):
            root = parent_ws
        else:
            root = default_prog

    if not (root / ".pde").is_dir():
        root.mkdir(parents=True, exist_ok=True)
        init_project(root)
    elif not (root / "dashboard.html").is_file():
        _safe_build_dashboard(root)
    return root


def _build_env(project_root: Path) -> dict[str, str]:
    """Construct portable environment variables for bin/env.sh."""
    env = os.environ.copy()
    env["PDE_ROOT"] = str(REPO_ROOT)
    env["PDE_PROJECT"] = str(project_root)
    env["PDE_ENV_SOURCE"] = str(TOOLS_DIR / "ENV_VERSION")
    py_paths = [
        str(REPO_ROOT),
        str(TOOLS_DIR),
        str(VENDOR_HYPEX_DIR),
    ]
    existing_py = env.get("PYTHONPATH", "")
    if existing_py:
        py_paths.append(existing_py)
    env["PYTHONPATH"] = os.pathsep.join(py_paths)

    bin_paths = [str(REPO_ROOT / "bin")]
    venv_bin = REPO_ROOT / ".venv" / "bin"
    if venv_bin.is_dir():
        bin_paths.append(str(venv_bin))
    existing_path = env.get("PATH", "")
    if existing_path:
        bin_paths.append(existing_path)
    env["PATH"] = os.pathsep.join(bin_paths)
    return env


def _safe_build_dashboard(
    project_root: Path,
    output_path: Path | None = None,
) -> tuple[str | None, dict[str, Any]]:
    """Build dashboard HTML and return (output_path_str, bundle)."""
    try:
        out_path, bundle = build_dashboard_html(
            project_root, output_path=output_path, standalone_mode=True
        )
        return str(out_path), bundle
    except Exception:
        return None, {}


def pde_exec(
    command: str,
    project_dir: str | None = None,
    auto_refresh_dashboard: bool = True,
) -> dict[str, Any]:
    """Execute a ``pde`` CLI command and return structured JSON output.

    Parameters
    ----------
    command:
        The ``pde`` CLI arguments (e.g., ``"doctor --json"`` or
        ``"genetics fetch TP53 --json"``). A leading ``"pde "`` prefix is
        automatically stripped if present.
    project_dir:
        Optional workspace directory override (defaults to ``$PDE_PROJECT``
        or ``.pde-workspace/default-program``).
    auto_refresh_dashboard:
        If True, incrementally rebuilds ``dashboard.html`` in the project
        workspace after executing the command.
    """
    project_root = resolve_project_root(project_dir)
    env = _build_env(project_root)

    tokens = shlex.split(command.strip())
    if tokens and tokens[0] in ("pde", "./bin/pde", "bin/pde"):
        tokens = tokens[1:]

    if not tokens:
        return {
            "ok": False,
            "exit_code": 2,
            "error": "Empty command passed to pde_exec",
            "project_dir": str(project_root),
        }

    cmd = [sys.executable, "-m", "pde.cli", "--project", str(project_root), *tokens]
    proc = subprocess.run(
        cmd,
        cwd=str(project_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    parsed_data: Any = None
    if stdout:
        try:
            parsed_data = json.loads(stdout)
        except ValueError:
            parsed_data = None

    stderr_json: Any = None
    if stderr:
        try:
            stderr_json = json.loads(stderr)
        except ValueError:
            stderr_json = None

    # Auto-refresh the interactive dashboard so every tool call keeps the UI live.
    dashboard_path: str | None = None
    if auto_refresh_dashboard and tokens[0] != "dashboard":
        dashboard_path, _ = _safe_build_dashboard(project_root)

    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "command": f"pde {' '.join(tokens)}",
        "project_dir": str(project_root),
        "data": parsed_data if parsed_data is not None else stdout,
        "stderr": stderr_json if stderr_json is not None else stderr,
        "dashboard_html": dashboard_path,
    }


def _normalize_workorder_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Ensure all 13 required YAML fields are populated with sensible defaults."""
    role = str(spec.get("requested_role") or "computational-biologist").strip()
    if role.startswith("pde-"):
        role = role.removeprefix("pde-")

    stage = spec.get("stage", 1)
    cycle = spec.get("cycle", 1)
    decision_question = spec.get(
        "decision_question",
        f"Execute {role} assessment for Stage {stage} Cycle {cycle}.",
    )

    raw_context = spec.get("context")
    if isinstance(raw_context, str):
        context = {"content": raw_context, "artifact_links": []}
    elif isinstance(raw_context, dict):
        context = {
            "content": str(raw_context.get("content", decision_question)),
            "artifact_links": list(raw_context.get("artifact_links", [])),
        }
    else:
        context = {"content": decision_question, "artifact_links": []}

    raw_deliverables = spec.get("deliverables")
    if not isinstance(raw_deliverables, dict):
        deliverables = {
            "layer_0_classes": [],
            "layer_1": [f"findings/{role}/stage{stage}-cycle{cycle}.md"],
        }
    else:
        deliverables = dict(raw_deliverables)
        if not any(
            k in deliverables
            for k in ("layer_0", "layer_0_classes", "required_classes", "layer_1")
        ):
            deliverables["layer_1"] = [f"findings/{role}/stage{stage}-cycle{cycle}.md"]

    raw_caps = spec.get("capabilities", [])
    if isinstance(raw_caps, dict):
        capabilities = list(raw_caps.get("required", [])) + list(raw_caps.get("optional", []))
    elif isinstance(raw_caps, list):
        capabilities = list(raw_caps)
    else:
        capabilities = []

    return {
        "decision_question": decision_question,
        "requested_role": role,
        "stage": stage,
        "cycle": cycle,
        "context": context,
        "dependencies": list(spec.get("dependencies", [])),
        "capabilities": capabilities,
        "deliverables": deliverables,
        "acceptance_criteria": spec.get(
            "acceptance_criteria",
            [
                "All Layer 0 artifacts have valid .meta.json and .analysis.json sidecars.",
                "All mandatory relays in .analysis.json appear in the Layer 1 findings report.",
                "All 10 mechanical validation checks pass via pde validate check.",
            ],
        ),
        "alert_policy": spec.get(
            "alert_policy",
            {
                "critical": "halt_and_escalate",
                "warning": "document_in_findings",
            },
        ),
        "priority": spec.get("priority", "normal"),
        "resource_class": spec.get("resource_class", "standard"),
        "report_to": spec.get("report_to", "discovery-lead"),
        **(
            {"liability_justification": spec["liability_justification"]}
            if "liability_justification" in spec
            else {}
        ),
    }


def _acquire_resource_lease(
    project_root: Path,
    resource_class: str,
    wo_id: str,
    revision: int,
    run_id: str,
    role: str,
) -> tuple[bool, Path | None, dict[str, Any] | None]:
    """Acquire a resource lease in .pde/control/leases/<resource_class>.json."""
    if not resource_class or resource_class == "standard":
        return True, None, None

    leases_dir = project_root / ".pde" / "control" / "leases"
    leases_dir.mkdir(parents=True, exist_ok=True)
    lease_path = leases_dir / f"{resource_class}.json"

    if lease_path.is_file():
        try:
            existing = json.loads(lease_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and existing.get("state") in ("held", "active"):
                holder_wo = existing.get("work_order_id") or existing.get("holder_wo_id")
                if holder_wo and holder_wo != wo_id:
                    return False, lease_path, existing
        except (OSError, ValueError):
            pass

    now_dt = datetime.now(timezone.utc)
    granted_at = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    lease_record = {
        "resource": resource_class,
        "resource_class": resource_class,
        "state": "held",
        "work_order_id": wo_id,
        "holder_wo_id": wo_id,
        "work_order_revision": revision,
        "run_id": run_id,
        "holder_run_id": run_id,
        "holder_agent": f"pde-{role}",
        "granted_at": granted_at,
        "acquired_at": granted_at,
        "ttl_minutes": 60,
        "expires_at": granted_at,
        "extensions": 0,
    }
    lease_path = controlstore.write_record(
        project_root, "lease", resource_class, lease_record
    )
    controlstore.append_event(
        project_root,
        {
            "type": "lease.acquired",
            "subject_id": resource_class,
            "actor": wo_id,
            "detail": {"run_id": run_id, "resource_class": resource_class},
        },
    )
    return True, lease_path, lease_record


def _release_resource_leases_for_wo(project_root: Path, wo_id: str) -> list[str]:
    """Release any active resource leases held by *wo_id*."""
    leases_dir = project_root / ".pde" / "control" / "leases"
    released: list[str] = []
    if not leases_dir.is_dir():
        return released

    for lease_file in sorted(leases_dir.glob("*.json")):
        try:
            data = json.loads(lease_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        holder = data.get("work_order_id") or data.get("holder_wo_id") if isinstance(data, dict) else None
        if isinstance(data, dict) and holder == wo_id and data.get("state") in ("held", "active"):
            rc = str(data.get("resource") or data.get("resource_class") or lease_file.stem)
            data["state"] = "released"
            data["released_at"] = _utc_now()
            lease_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            released.append(rc)
            controlstore.append_event(
                project_root,
                {
                    "type": "lease.released",
                    "subject_id": rc,
                    "actor": wo_id,
                    "detail": {"resource_class": rc},
                },
            )
    return released


def pde_dispatch_workorder(
    spec: dict[str, Any],
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Execute the 4-step Work Order intake ceremony and prepare a specialist brief.

    1. Writes the work-order YAML and runs ``pde workorder create --from <yaml> --commit --json``.
    2. Freezes the checksummed context snapshot in ``.pde/control/contexts/<WO-ID>-r<rev>.json``.
    3. Checks/acquires ``.pde/control/leases/<resource_class>.json`` if ``resource_class != "standard"``.
    4. Creates the run record (``pde run create <WO-ID> --json``), transitions the run
       ``queued -> starting -> running``, and transitions the work order
       ``committed -> queued -> in_progress``.
    """
    project_root = resolve_project_root(project_dir)
    normalized = _normalize_workorder_spec(spec)
    role = normalized["requested_role"]
    resource_class = normalized["resource_class"]

    # Check if resource lease is busy before creating/starting a run
    leases_dir = project_root / ".pde" / "control" / "leases"
    if resource_class and resource_class != "standard":
        lease_candidate = leases_dir / f"{resource_class}.json"
        if lease_candidate.is_file():
            try:
                existing_lease = json.loads(lease_candidate.read_text(encoding="utf-8"))
                if isinstance(existing_lease, dict) and existing_lease.get("state") in ("held", "active"):
                    holder_wo = existing_lease.get("work_order_id") or existing_lease.get("holder_wo_id")
                    holder_run = existing_lease.get("run_id") or existing_lease.get("holder_run_id")
                    return {
                        "ok": False,
                        "status": "RESOURCE_BUSY",
                        "resource_class": resource_class,
                        "lease_holder": existing_lease,
                        "remedy": (
                            f"Resource class '{resource_class}' is currently leased by "
                            f"{holder_wo} ({holder_run}). "
                            "Wait for that work order to validate/complete before dispatching."
                        ),
                    }
            except (OSError, ValueError):
                pass

    specs_dir = project_root / ".pde" / "control" / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    yaml_path = specs_dir / f"wo-spec-{ts}-{role}.yaml"
    yaml_path.write_text(yaml.safe_dump(normalized, sort_keys=False), encoding="utf-8")

    # Step 1 & 2: Create and commit Work Order (creates context snapshot)
    create_res = pde_exec(
        f"workorder create --from {shlex.quote(str(yaml_path))} --commit --json",
        project_dir=str(project_root),
        auto_refresh_dashboard=False,
    )
    if not create_res["ok"] or not isinstance(create_res["data"], dict):
        return {
            "ok": False,
            "status": "CREATE_FAILED",
            "error": create_res.get("stderr") or create_res.get("data"),
        }

    wo_data = create_res["data"]
    wo_id = wo_data["id"]
    revision = wo_data.get("revision", 1)

    # Step 3: Transition WO committed -> queued -> in_progress
    pde_exec(
        f"workorder transition {wo_id} queued --json",
        project_dir=str(project_root),
        auto_refresh_dashboard=False,
    )
    pde_exec(
        f"workorder transition {wo_id} in_progress --json",
        project_dir=str(project_root),
        auto_refresh_dashboard=False,
    )

    # Step 4: Create run and transition queued -> starting -> running
    run_res = pde_exec(
        f"run create {wo_id} --revision {revision} --json",
        project_dir=str(project_root),
        auto_refresh_dashboard=False,
    )
    if not run_res["ok"] or not isinstance(run_res["data"], dict):
        return {
            "ok": False,
            "status": "RUN_CREATE_FAILED",
            "work_order_id": wo_id,
            "error": run_res.get("stderr") or run_res.get("data"),
        }

    run_id = run_res["data"]["run_id"]
    pde_exec(
        f"run transition {run_id} starting --json",
        project_dir=str(project_root),
        auto_refresh_dashboard=False,
    )
    pde_exec(
        f"run transition {run_id} running --json",
        project_dir=str(project_root),
        auto_refresh_dashboard=False,
    )

    # Acquire resource lease if non-standard
    _, lease_path, lease_record = _acquire_resource_lease(
        project_root, resource_class, wo_id, revision, run_id, role
    )

    snapshot_path = (
        project_root / ".pde" / "control" / "contexts" / f"{wo_id}-r{revision}.json"
    )
    wo_record_path = (
        project_root / ".pde" / "control" / "work-orders" / f"{wo_id}-r{revision}.json"
    )

    controlstore.append_event(
        project_root,
        {
            "type": "dispatch.subagent",
            "subject_id": wo_id,
            "revision": revision,
            "actor": normalized.get("report_to", "discovery-lead"),
            "detail": {
                "requested_role": role,
                "subagent_name": f"pde-{role}",
                "run_id": run_id,
                "decision_question": normalized["decision_question"],
            },
        },
    )

    # Build specialist dispatch brief
    layer_0_req = (
        normalized["deliverables"].get("layer_0")
        or normalized["deliverables"].get("layer_0_classes")
        or normalized["deliverables"].get("required_classes")
        or []
    )
    layer_1_req = normalized["deliverables"].get("layer_1") or []

    rel_wo_record = f".pde/control/work-orders/{wo_id}-r{revision}.json"
    rel_snapshot = f".pde/control/contexts/{wo_id}-r{revision}.json"

    specialist_brief = (
        f"# WORK ORDER DISPATCH: {wo_id} (Revision {revision} | Run {run_id})\n"
        f"- **Assigned Role**: `{role}` (Subagent: `pde-{role}`)\n"
        f"- **Stage / Cycle**: Stage {normalized['stage']}, Cycle {normalized['cycle']}\n"
        f"- **Work Order Record**: `{rel_wo_record}`\n"
        f"- **Context Snapshot**: `{rel_snapshot}`\n\n"
        f"## Decision Question\n{normalized['decision_question']}\n\n"
        f"## Context\n{normalized['context'].get('content', '')}\n\n"
        f"## Required Deliverables\n"
        f"- **Layer 0 Artifact Classes**: `{json.dumps(layer_0_req)}`\n"
        f"- **Layer 1 Findings Reports**: `{json.dumps(layer_1_req)}`\n\n"
        f"## Mandatory Execution Rules\n"
        f"1. Source `bin/env.sh` from the repository root and set `PDE_PROJECT` to the active workspace.\n"
        f"2. Run both Phase 1 (`fetch`/`run`/`compute`) and Phase 2 (`analyze`) for every domain tool.\n"
        f"3. Every Layer 1 finding report MUST include `## Summary`, `## Verdict`, and `## Evidence` headings, "
        f"cite `{wo_id}` (or `r{revision}`), include inline `{{source: raw/...}}` tags for quantitative claims, "
        f"and surface every `mandatory_relays` code from `.analysis.json` as `**Relay: \\`<code>\\`**`.\n"
        f"4. Run `pde validate check {wo_id} --dry-run` before finishing to verify all 10 checks pass.\n"
    )

    dashboard_path, _ = _safe_build_dashboard(project_root)

    return {
        "ok": True,
        "status": "DISPATCHED",
        "work_order_id": wo_id,
        "revision": revision,
        "run_id": run_id,
        "requested_role": role,
        "subagent_name": f"pde-{role}",
        "resource_class": resource_class,
        "lease": lease_record,
        "lease_path": str(lease_path) if lease_path else None,
        "context_snapshot_path": str(snapshot_path),
        "work_order_record_path": str(wo_record_path),
        "specialist_brief": specialist_brief,
        "dashboard_html": dashboard_path,
    }


def pde_validate_and_gate(
    work_order_id: str,
    run_id: str | None = None,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Run the 10-check mechanical validation gate and drive the correction loop.

    Transitions the work order to ``submitted`` (if not already in ``submitted``),
    executes ``pde validate check <WO-ID> --json``, and routes the outcome:
    - ``PASSED`` (``pass`` or ``pass_with_warnings``): transitions run to ``succeeded``,
      releases any held resource lease, refreshes ``dashboard.html``.
    - ``DATA_INTEGRITY_FAILURE``: any failed check has ``kind == "DATA_INTEGRITY"``;
      transitions run to ``failed`` (``contract_failure``), halts without retry.
    - ``CORRECTION_REQUIRED``: mechanical defect (``COMPLETENESS``, ``FORMAT``,
      ``CONSISTENCY``) with ``correction_cycle <= 2``; transitions work order
      ``validation_failed -> in_progress`` and returns a structured ``correction_prompt``.
    """
    project_root = resolve_project_root(project_dir)

    # Locate latest WO record
    wo_records = controlstore.list_records(
        project_root, "work-order", lambda r: r.get("id") == work_order_id
    )
    if not wo_records:
        return {
            "ok": False,
            "status": "NOT_FOUND",
            "error": f"Work order {work_order_id} not found in {project_root}",
        }
    wo_record = max(wo_records, key=lambda r: r.get("revision", 0))
    revision = wo_record["revision"]
    wo_state = wo_record.get("state")

    # Resolve run_id if not explicitly supplied
    if not run_id:
        runs = controlstore.list_records(
            project_root,
            "run",
            lambda r: (
                r.get("work_order_id") == work_order_id
                and r.get("work_order_revision") == revision
            ),
        )
        if runs:
            run_id = max(runs, key=lambda r: r.get("created_at", "")).get("run_id")

    # Bring work order to 'submitted' state if needed
    if wo_state == "committed":
        pde_exec(
            f"workorder transition {work_order_id} queued --json",
            project_dir=str(project_root),
            auto_refresh_dashboard=False,
        )
        wo_state = "queued"
    if wo_state == "queued":
        pde_exec(
            f"workorder transition {work_order_id} in_progress --json",
            project_dir=str(project_root),
            auto_refresh_dashboard=False,
        )
        wo_state = "in_progress"
    if wo_state == "validation_failed":
        pde_exec(
            f"workorder transition {work_order_id} in_progress --json",
            project_dir=str(project_root),
            auto_refresh_dashboard=False,
        )
        wo_state = "in_progress"
    if wo_state == "in_progress":
        pde_exec(
            f"workorder transition {work_order_id} submitted --json",
            project_dir=str(project_root),
            auto_refresh_dashboard=False,
        )
        wo_state = "submitted"

    # Run the 10-check validator
    val_res = pde_exec(
        f"validate check {work_order_id} --revision {revision} --json",
        project_dir=str(project_root),
        auto_refresh_dashboard=False,
    )
    val_data = val_res.get("data") if isinstance(val_res.get("data"), dict) else {}
    result = val_data.get("result", "fail")
    checks = val_data.get("checks", [])
    failed_checks = [c for c in checks if c.get("result") == "fail"]
    failed_names = [c.get("name", "") for c in failed_checks]

    # Case 1: Validation Passed
    if result in ("pass", "pass_with_warnings"):
        if run_id:
            try:
                run_rec = controlstore.read_record(project_root, "run", run_id)
                r_state = run_rec.get("state")
                if r_state == "queued":
                    pde_exec(
                        f"run transition {run_id} starting --json",
                        project_dir=str(project_root),
                        auto_refresh_dashboard=False,
                    )
                    r_state = "starting"
                if r_state == "starting":
                    pde_exec(
                        f"run transition {run_id} running --json",
                        project_dir=str(project_root),
                        auto_refresh_dashboard=False,
                    )
                    r_state = "running"
                if r_state == "running":
                    pde_exec(
                        f"run transition {run_id} succeeded --json",
                        project_dir=str(project_root),
                        auto_refresh_dashboard=False,
                    )
            except Exception:
                pass

        released_leases = _release_resource_leases_for_wo(project_root, work_order_id)
        dashboard_path, _ = _safe_build_dashboard(project_root)

        return {
            "ok": True,
            "status": "PASSED",
            "work_order_id": work_order_id,
            "revision": revision,
            "run_id": run_id,
            "validation_result": result,
            "checks": checks,
            "checks_failed": [],
            "released_leases": released_leases,
            "ready_for_scientific_review": True,
            "dashboard_html": dashboard_path,
        }

    # Case 2: Data Integrity Failure -> Halt immediately, no retry allowed
    data_integrity_failures = [
        c for c in failed_checks if c.get("kind") == "DATA_INTEGRITY"
    ]
    if data_integrity_failures:
        detail_msg = "; ".join(
            f"{c.get('name')}: {c.get('detail')}" for c in data_integrity_failures
        )
        if run_id:
            try:
                run_rec = controlstore.read_record(project_root, "run", run_id)
                if run_rec.get("state") == "running":
                    pde_exec(
                        f"run transition {run_id} failed --failure-class contract_failure "
                        f"--detail {shlex.quote(detail_msg[:240])} --json",
                        project_dir=str(project_root),
                        auto_refresh_dashboard=False,
                    )
            except Exception:
                pass

        released_leases = _release_resource_leases_for_wo(project_root, work_order_id)
        controlstore.append_event(
            project_root,
            {
                "type": "validation.failed",
                "subject_id": work_order_id,
                "revision": revision,
                "actor": "validator",
                "detail": {
                    "defect_class": "data_integrity",
                    "checks_failed": failed_names,
                    "detail": detail_msg,
                },
            },
        )
        dashboard_path, _ = _safe_build_dashboard(project_root)

        return {
            "ok": False,
            "status": "DATA_INTEGRITY_FAILURE",
            "work_order_id": work_order_id,
            "revision": revision,
            "run_id": run_id,
            "validation_result": result,
            "checks": checks,
            "checks_failed": failed_names,
            "retry_allowed": False,
            "released_leases": released_leases,
            "escalation_message": (
                f"CRITICAL DATA INTEGRITY FAILURE on {work_order_id}-r{revision}: {detail_msg}. "
                "Automatic retry is prohibited. Escalate to Discovery Lead and record in decision-log.md."
            ),
            "dashboard_html": dashboard_path,
        }

    # Case 3: Mechanical Defect (COMPLETENESS, FORMAT, CONSISTENCY) -> up to 2 correction cycles
    wo_identifier = f"{work_order_id}-r{revision}"
    latest_wo = controlstore.read_record(project_root, "work-order", wo_identifier)
    correction_cycle = int(latest_wo.get("correction_cycle", 0)) + 1
    latest_wo["correction_cycle"] = correction_cycle
    controlstore.write_record(project_root, "work-order", wo_identifier, latest_wo)

    if correction_cycle <= 2:
        # Transition validation_failed -> in_progress for in-place specialist correction
        pde_exec(
            f"workorder transition {work_order_id} in_progress --json",
            project_dir=str(project_root),
            auto_refresh_dashboard=False,
        )
        bullet_lines = [
            f"- **{c.get('name')}** (`{c.get('kind', 'MECHANICAL')}`): {c.get('detail', '')}"
            for c in failed_checks
        ]
        correction_prompt = (
            f"CORRECTION REQUIRED {work_order_id} (Revision {revision}, Cycle {correction_cycle}/2):\n"
            f"Mechanical validation (`pde validate check {work_order_id}`) failed on the following check(s):\n"
            + "\n".join(bullet_lines)
            + "\n\nPlease fix these defects in-place in the workspace and verify with "
            f"`pde validate check {work_order_id} --dry-run` before reporting completion."
        )
        controlstore.append_event(
            project_root,
            {
                "type": "correction_returned",
                "subject_id": work_order_id,
                "revision": revision,
                "actor": "validator",
                "detail": {
                    "correction_cycle": correction_cycle,
                    "checks_failed": failed_names,
                },
            },
        )
        dashboard_path, _ = _safe_build_dashboard(project_root)

        return {
            "ok": False,
            "status": "CORRECTION_REQUIRED",
            "work_order_id": work_order_id,
            "revision": revision,
            "run_id": run_id,
            "validation_result": result,
            "checks": checks,
            "checks_failed": failed_names,
            "retry_allowed": True,
            "correction_cycle": correction_cycle,
            "correction_prompt": correction_prompt,
            "dashboard_html": dashboard_path,
        }

    # Exceeded 2 correction cycles
    detail_msg = f"Mechanical validation failed after {correction_cycle - 1} correction cycles: {', '.join(failed_names)}"
    if run_id:
        try:
            run_rec = controlstore.read_record(project_root, "run", run_id)
            if run_rec.get("state") == "running":
                pde_exec(
                    f"run transition {run_id} failed --failure-class contract_failure "
                    f"--detail {shlex.quote(detail_msg[:240])} --json",
                    project_dir=str(project_root),
                    auto_refresh_dashboard=False,
                )
        except Exception:
            pass

    released_leases = _release_resource_leases_for_wo(project_root, work_order_id)
    dashboard_path, _ = _safe_build_dashboard(project_root)

    return {
        "ok": False,
        "status": "MAX_CORRECTIONS_EXCEEDED",
        "work_order_id": work_order_id,
        "revision": revision,
        "run_id": run_id,
        "validation_result": result,
        "checks": checks,
        "checks_failed": failed_names,
        "retry_allowed": False,
        "correction_cycle": correction_cycle,
        "released_leases": released_leases,
        "escalation_message": detail_msg,
        "dashboard_html": dashboard_path,
    }


def pde_render_dashboard(
    project_dir: str | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Build the self-contained PDE Interactive Scientific Dashboard HTML."""
    project_root = resolve_project_root(project_dir)
    out = Path(output_path).expanduser().resolve() if output_path else None
    out_path, bundle = build_dashboard_html(
        project_root, output_path=out, standalone_mode=True
    )
    prog = bundle.get("program", {})
    return {
        "ok": True,
        "status": "BUILT",
        "output_path": str(out_path),
        "program_name": prog.get("name"),
        "stage": prog.get("stage"),
        "summary_metrics": prog.get("summary_metrics", {}),
    }
