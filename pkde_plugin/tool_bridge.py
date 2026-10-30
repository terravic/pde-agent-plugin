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
1. ``pkde_exec`` -- Execute any two-phase or control-plane ``pkde`` CLI command.
2. ``pkde_dispatch_workorder`` -- Atomic 4-step Work Order intake, snapshot, lease, and run start.
3. ``pkde_validate_and_gate`` -- 10-check mechanical validation gate and correction loop driver.
4. ``pkde_render_dashboard`` -- Build the self-contained multi-agent and scientific dashboard HTML.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
VENDOR_HYPEX_DIR = TOOLS_DIR / "vendor" / "hypex"

for _p in (str(REPO_ROOT), str(TOOLS_DIR), str(VENDOR_HYPEX_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pkde.commands.dashboard import (  # noqa: E402
    bootstrap_prompt_session,
    build_dashboard_html,
    ensure_dashboard_server,
    log_agent_message,
    record_active_project,
)
from pkde.core import controlstore  # noqa: E402
from pkde.core.context import init_project  # noqa: E402


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_pkde_python() -> str:
    """Return the best Python interpreter for invoking pkde.cli."""
    env_py = os.environ.get("PKDE_PYTHON", "").strip()
    if env_py and Path(env_py).is_file() and os.access(env_py, os.X_OK):
        return env_py
    if importlib.util.find_spec("click") is not None:
        return sys.executable
    for candidate in (
        REPO_ROOT / ".venv" / "bin" / "python",
        REPO_ROOT / ".venv" / "Scripts" / "python.exe",
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return sys.executable


def _resolve_active_pointer_workspace() -> Path | None:
    ptr = REPO_ROOT / ".pkde-workspace" / "active-project.json"
    if not ptr.is_file():
        return None
    try:
        data = json.loads(ptr.read_text(encoding="utf-8"))
        raw_ptr = str(data.get("project_root", "")).strip()
        if not raw_ptr or raw_ptr == ".":
            return None
        cand_path = Path(raw_ptr).expanduser()
        cand = (
            cand_path.resolve()
            if cand_path.is_absolute()
            else (REPO_ROOT / cand_path).resolve()
        )
        if cand != REPO_ROOT and (cand / ".pkde").is_dir():
            return cand
    except Exception:
        pass
    return None


def resolve_project_root(project_dir: str | Path | None = None) -> Path:
    """Resolve and initialize the active PkDE project workspace root."""
    if project_dir:
        root = Path(project_dir).expanduser().resolve()
    elif os.environ.get("PKDE_PROJECT"):
        root = Path(os.environ["PKDE_PROJECT"]).expanduser().resolve()
    else:
        active_ws = _resolve_active_pointer_workspace()
        if active_ws is not None:
            root = active_ws
        else:
            root = (REPO_ROOT / ".pkde-workspace" / "default-program").resolve()

    if not (root / ".pkde").is_dir():
        root.mkdir(parents=True, exist_ok=True)
        init_project(root)
    elif not (root / "dashboard.html").is_file():
        _safe_build_dashboard(root)

    if root.is_relative_to(REPO_ROOT) and root != REPO_ROOT:
        try:
            record_active_project(root)
            if os.environ.get("PKDE_AUTO_SERVE_DASHBOARD", "0") == "1":
                ensure_dashboard_server(root)
        except Exception:
            pass
    return root


_SPEC_SEQ = 0


def _build_env(
    project_root: Path,
    *,
    work_order_id: str | None = None,
    agent_role: str | None = None,
    run_id: str | None = None,
    agent_slug: str | None = None,
) -> dict[str, str]:
    """Construct portable, hermetic environment variables for bin/env.sh."""
    env = os.environ.copy()
    env["PKDE_ROOT"] = str(REPO_ROOT)
    env["PKDE_PROJECT"] = str(project_root)
    env["PKDE_ENV_SOURCE"] = str(TOOLS_DIR / "ENV_VERSION")
    if work_order_id:
        env["PKDE_WORK_ORDER_ID"] = str(work_order_id)
    if run_id:
        env["PKDE_RUN_ID"] = str(run_id)
    if agent_role:
        clean_role = str(agent_role).removeprefix("pkde-")
        env["PKDE_AGENT_ROLE"] = clean_role
        if not agent_slug and work_order_id:
            agent_slug = f"pkde-{clean_role}-{str(work_order_id).lower()}"
        elif not agent_slug:
            agent_slug = f"pkde-{clean_role}"
    if agent_slug:
        env["PKDE_AGENT_SLUG"] = str(agent_slug)

    py_paths = [
        str(REPO_ROOT),
        str(TOOLS_DIR),
        str(VENDOR_HYPEX_DIR),
    ]
    extra_py = env.get("PKDE_EXTRA_PYTHONPATH", "").strip()
    if extra_py:
        py_paths.append(extra_py)
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
    """Build dashboard HTML and return (output_path_str, bundle).

    A rendering failure must not abort scientific work, but it is recorded
    as a ``dashboard.build_failed`` control-plane event (and returned in the
    bundle under ``"error"``) rather than being swallowed.
    """
    try:
        out_path, bundle = build_dashboard_html(
            project_root, output_path=output_path, standalone_mode=True
        )
        return str(out_path), bundle
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
        try:
            controlstore.append_event(
                project_root,
                {
                    "type": "dashboard.build_failed",
                    "subject_id": "dashboard",
                    "actor": "tool-bridge",
                    "detail": {"error": err[:500]},
                },
            )
        except OSError:
            pass  # control dir not writable; error still returned below
        return None, {"error": err}


def pkde_exec(
    command: str | list[str],
    project_dir: str | None = None,
    auto_refresh_dashboard: bool = True,
    work_order_id: str | None = None,
    agent_role: str | None = None,
    run_id: str | None = None,
    agent_slug: str | None = None,
) -> dict[str, Any]:
    """Execute a ``pkde`` CLI command and return structured JSON output."""
    project_root = resolve_project_root(project_dir)
    env = _build_env(
        project_root,
        work_order_id=work_order_id,
        agent_role=agent_role,
        run_id=run_id,
        agent_slug=agent_slug,
    )

    if isinstance(command, (list, tuple)):
        tokens = [str(x) for x in command]
    else:
        tokens = shlex.split(str(command).strip())
    if tokens and tokens[0] in ("pkde", "./bin/pkde", "bin/pkde"):
        tokens = tokens[1:]

    if not tokens:
        return {
            "ok": False,
            "exit_code": 2,
            "error": "Empty command passed to pkde_exec",
            "project_dir": str(project_root),
        }

    # Prevent foreground HTTP server commands from blocking the agent harness indefinitely.
    if len(tokens) >= 2 and tokens[0] == "dashboard" and tokens[1] == "serve":
        tokens = ["dashboard", "start", *tokens[2:]]

    py_exe = _resolve_pkde_python()
    timeout_sec = float(os.environ.get("PKDE_EXEC_TIMEOUT", "180"))
    cmd = [py_exe, "-m", "pkde.cli", "--project", str(project_root), *tokens]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(project_root),
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "exit_code": 124,
            "command": f"pkde {' '.join(tokens)}",
            "project_dir": str(project_root),
            "data": None,
            "stderr": {
                "error_code": "COMMAND_TIMEOUT",
                "message": f"pkde command timed out after {timeout_sec:.0f}s",
                "stdout_partial": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
            },
            "dashboard_html": None,
        }

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
        "command": f"pkde {' '.join(tokens)}",
        "project_dir": str(project_root),
        "work_order_id": env.get("PKDE_WORK_ORDER_ID"),
        "agent_role": env.get("PKDE_AGENT_ROLE"),
        "run_id": env.get("PKDE_RUN_ID"),
        "data": parsed_data if parsed_data is not None else stdout,
        "stderr": stderr_json if stderr_json is not None else stderr,
        "dashboard_html": dashboard_path,
    }


#: Canonical PkDE persona slugs (without the ``pkde-`` prefix).  Every
#: dispatched work order must target one of these so the emitted
#: ``subagent_invocation["TypeName"]`` (``pkde-<role>``) resolves to a real
#: agent definition under ``.agents/plugins/pharmakon-discovery-engine/agents/``.
#: ``tests/test_skill_contract.py`` asserts this set matches the agent files.
PKDE_AGENT_ROLES: frozenset[str] = frozenset(
    {
        "admet-dmpk-scientist",
        "bootstrapper",
        "computational-biologist",
        "computational-chemist",
        "experimental-biologist",
        "finding-validator",
        "head-of-discovery",
        "hypex-evolution",
        "hypex-generation",
        "hypex-meta-review",
        "hypex-proximity",
        "hypex-reflection",
        "hypex-supervisor",
        "hypex-tournament",
        "medicinal-chemist",
        "preclinical-toxicologist",
        "project-curator",
        "regulatory-scientist",
        "research-operations-controller",
        "science-program-lead",
        "scientific-reviewer",
        "structural-biologist",
    }
)

#: Default exclusive-resource lease TTL (minutes).  Override per process with
#: ``PKDE_LEASE_TTL_MINUTES``; holders extend via
#: ``pkde_manage_cohort(action="renew_lease")``.
DEFAULT_LEASE_TTL_MINUTES = 60


class WorkOrderSpecError(ValueError):
    """Raised when a work-order spec is missing scientifically required content."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = list(errors)


def _exec_checked(
    command: str,
    project_root: Path,
    step: str,
) -> dict[str, Any]:
    """Run a control-plane ``pkde`` command and raise if it fails.

    State transitions are not optional bookkeeping: if one fails, the work
    order / run is not in the state the caller assumes, so the failure must
    surface instead of being ignored.
    """
    res = pkde_exec(command, project_dir=str(project_root), auto_refresh_dashboard=False)
    if not res.get("ok"):
        raise _ControlPlaneError(step, command, res.get("stderr") or res.get("data"))
    return res


class _ControlPlaneError(RuntimeError):
    def __init__(self, step: str, command: str, detail: Any) -> None:
        super().__init__(f"{step} failed: pkde {command}: {detail}")
        self.step = step
        self.command = command
        self.detail = detail

    def as_result(self, **extra: Any) -> dict[str, Any]:
        return {
            "ok": False,
            "status": "TRANSITION_FAILED",
            "failed_step": self.step,
            "command": f"pkde {self.command}",
            "error": self.detail,
            **extra,
        }


def _resolve_role(spec: dict[str, Any]) -> str | None:
    raw = spec.get("requested_role") or spec.get("role") or spec.get("assigned_role")
    if raw is None:
        return None
    role = str(raw).strip()
    return role.removeprefix("pkde-") if role else None


def _layer0_declared(deliverables: dict[str, Any]) -> bool:
    return any(
        deliverables.get(k)
        for k in (
            "layer_0",
            "layer_0_classes",
            "required_classes",
            "authorized_classes",
            "layer_0_classes_optional",
        )
    )


def _normalize_workorder_spec(
    spec: dict[str, Any],
    *,
    strict: bool = True,
) -> dict[str, Any]:
    """Normalize a work-order spec into the 13 CLI-required YAML fields.

    With ``strict=True`` (all new dispatches), the scientifically meaningful
    fields are *required* rather than defaulted:

    - ``requested_role`` (alias ``role``/``assigned_role``) must be one of
      :data:`PKDE_AGENT_ROLES`;
    - ``decision_question`` must be a non-empty string;
    - ``deliverables`` must declare at least one Layer 1 findings report and
      at least one Layer 0 artifact class, unless the deliverables mapping
      sets ``synthesis_only: true`` (review/synthesis work orders whose
      evidence is other work orders' Layer 0 artifacts).

    Process fields (``stage``, ``cycle``, ``priority``, ``resource_class``,
    ``alert_policy``, ``acceptance_criteria``, ``report_to``) keep their
    documented defaults because they carry no scientific content.

    ``strict=False`` is used only to rebuild briefs from records that were
    already validated and committed.
    """
    if not isinstance(spec, dict):
        raise WorkOrderSpecError(
            [f"work-order spec must be a mapping, got {type(spec).__name__}"]
        )
    errors: list[str] = []

    role = _resolve_role(spec)
    if not role:
        errors.append("requested_role is required (one of: pkde-" + ", pkde-".join(sorted(PKDE_AGENT_ROLES)) + ")")
    elif role not in PKDE_AGENT_ROLES:
        errors.append(
            f"requested_role 'pkde-{role}' is not a PkDE agent; valid roles: "
            + ", ".join(f"pkde-{r}" for r in sorted(PKDE_AGENT_ROLES))
        )

    raw_stage = spec.get("stage", 1)
    if isinstance(raw_stage, str):
        digits = "".join(ch for ch in raw_stage if ch.isdigit())
        stage = int(digits) if digits else 1
    else:
        stage = int(raw_stage)
    cycle = int(spec.get("cycle", 1))

    raw_question = spec.get("decision_question")
    decision_question = str(raw_question).strip() if raw_question is not None else ""
    if not decision_question:
        errors.append("decision_question is required and must be non-empty")

    raw_deliverables = spec.get("deliverables")
    if raw_deliverables is None:
        errors.append(
            "deliverables are required: declare layer_1 findings report path(s) "
            "and layer_0_classes (or set synthesis_only: true for synthesis/review work orders)"
        )
    elif isinstance(raw_deliverables, list):
        l1 = [p for p in raw_deliverables if str(p).startswith("findings/")]
        l0 = [p for p in raw_deliverables if str(p).startswith("raw/")]
        if not l1:
            errors.append("deliverables must include at least one findings/<...>.md Layer 1 report")
        if not l0:
            errors.append(
                "deliverables must include at least one raw/<class>/... Layer 0 artifact "
                "(list form cannot declare synthesis_only; use the mapping form)"
            )
    elif isinstance(raw_deliverables, dict):
        if not raw_deliverables.get("layer_1"):
            errors.append("deliverables.layer_1 must list at least one findings report path")
        if not _layer0_declared(raw_deliverables) and raw_deliverables.get("synthesis_only") is not True:
            errors.append(
                "deliverables must declare layer_0_classes (Layer 0 evidence) "
                "or explicitly set synthesis_only: true"
            )
    else:
        errors.append(
            f"deliverables must be a mapping or list, got {type(raw_deliverables).__name__}"
        )

    if strict and errors:
        raise WorkOrderSpecError(errors)

    role = role or "unassigned"
    if not decision_question:
        decision_question = str(raw_question or "")

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

    if isinstance(raw_deliverables, list):
        l0_paths = [str(p) for p in raw_deliverables if str(p).startswith("raw/")]
        l1_paths = [str(p) for p in raw_deliverables if str(p).startswith("findings/")]
        l0_classes: list[str] = []
        for p in l0_paths:
            parts = Path(p).parts
            if len(parts) >= 2 and parts[1] not in l0_classes:
                l0_classes.append(parts[1])
        deliverables = {
            "layer_0": l0_paths,
            "layer_0_classes": l0_classes,
            "layer_1": l1_paths,
        }
    elif isinstance(raw_deliverables, dict):
        deliverables = dict(raw_deliverables)
    else:
        # Only reachable with strict=False on a legacy committed record;
        # the validator's deliverables_schema check will flag it.
        deliverables = {}

    raw_caps = spec.get("capabilities", [])
    if isinstance(raw_caps, dict):
        capabilities = list(raw_caps.get("required", [])) + list(raw_caps.get("optional", []))
    elif isinstance(raw_caps, list):
        capabilities = list(raw_caps)
    else:
        capabilities = []

    raw_deps = spec.get("dependencies") or spec.get("depends_on") or []

    return {
        "decision_question": decision_question,
        "requested_role": role,
        "stage": stage,
        "cycle": cycle,
        "context": context,
        "dependencies": list(raw_deps),
        "capabilities": capabilities,
        "deliverables": deliverables,
        "acceptance_criteria": spec.get(
            "acceptance_criteria",
            [
                "All Layer 0 artifacts have valid .meta.json and .analysis.json sidecars.",
                "All mandatory relays in .analysis.json appear in the Layer 1 findings report.",
                "All 10 mechanical validation checks pass via pkde validate check.",
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


def _lease_ttl_minutes() -> int:
    raw = os.environ.get("PKDE_LEASE_TTL_MINUTES", "").strip()
    if not raw:
        return DEFAULT_LEASE_TTL_MINUTES
    try:
        ttl = int(raw)
    except ValueError as exc:
        raise ValueError(f"PKDE_LEASE_TTL_MINUTES must be a positive integer, got {raw!r}") from exc
    if ttl < 1:
        raise ValueError(f"PKDE_LEASE_TTL_MINUTES must be a positive integer, got {raw!r}")
    return ttl


def _parse_utc(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _expire_lease_if_stale(
    project_root: Path,
    lease_path: Path,
    lease: dict[str, Any],
) -> bool:
    """Mark a held lease ``expired`` if its ``expires_at`` is in the past.

    Returns True when the lease was expired by this call.  A lease without a
    parseable ``expires_at`` is *not* expired (it is reported as held), so a
    malformed record can never silently free an exclusive resource.
    """
    expires = _parse_utc(str(lease.get("expires_at", "")))
    if expires is None or expires > datetime.now(timezone.utc):
        return False
    lease["state"] = "expired"
    lease["expired_at"] = _utc_now()
    lease_path.write_text(json.dumps(lease, indent=2) + "\n", encoding="utf-8")
    controlstore.append_event(
        project_root,
        {
            "type": "lease.expired",
            "subject_id": str(lease.get("resource") or lease_path.stem),
            "actor": "lease-manager",
            "detail": {
                "work_order_id": lease.get("work_order_id"),
                "run_id": lease.get("run_id"),
                "expires_at": lease.get("expires_at"),
            },
        },
    )
    return True


def _is_resource_lease_busy(
    project_root: Path,
    resource_class: str,
    exclude_wo_id: str | None = None,
) -> tuple[bool, dict[str, Any] | None]:
    """Return (is_busy, existing_lease) for a resource_class.

    Held leases past ``expires_at`` are expired (and logged) here, so a
    crashed subagent can no longer block an exclusive resource forever.
    """
    if not resource_class or resource_class == "standard":
        return False, None
    lease_candidate = project_root / ".pkde" / "control" / "leases" / f"{resource_class}.json"
    if not lease_candidate.is_file():
        return False, None
    try:
        existing_lease = json.loads(lease_candidate.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return True, {
            "resource": resource_class,
            "state": "unreadable",
            "path": str(lease_candidate),
            "error": str(exc),
            "remedy": "inspect or remove the corrupt lease file before dispatching",
        }
    if isinstance(existing_lease, dict) and existing_lease.get("state") in ("held", "active"):
        holder_wo = existing_lease.get("work_order_id") or existing_lease.get("holder_wo_id")
        if holder_wo and holder_wo != exclude_wo_id:
            if _expire_lease_if_stale(project_root, lease_candidate, existing_lease):
                return False, None
            return True, existing_lease
    return False, None


def _acquire_resource_lease(
    project_root: Path,
    resource_class: str,
    wo_id: str,
    revision: int,
    run_id: str,
    role: str,
) -> tuple[bool, Path | None, dict[str, Any] | None]:
    """Acquire a resource lease in .pkde/control/leases/<resource_class>.json."""
    if not resource_class or resource_class == "standard":
        return True, None, None

    leases_dir = project_root / ".pkde" / "control" / "leases"
    leases_dir.mkdir(parents=True, exist_ok=True)
    lease_path = leases_dir / f"{resource_class}.json"

    busy, existing = _is_resource_lease_busy(project_root, resource_class, exclude_wo_id=wo_id)
    if busy:
        return False, lease_path, existing

    ttl = _lease_ttl_minutes()
    now_dt = datetime.now(timezone.utc)
    granted_at = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    expires_at = (now_dt + timedelta(minutes=ttl)).strftime("%Y-%m-%dT%H:%M:%SZ")
    lease_record = {
        "resource": resource_class,
        "resource_class": resource_class,
        "state": "held",
        "work_order_id": wo_id,
        "holder_wo_id": wo_id,
        "work_order_revision": revision,
        "run_id": run_id,
        "holder_run_id": run_id,
        "holder_agent": f"pkde-{role}",
        "granted_at": granted_at,
        "acquired_at": granted_at,
        "ttl_minutes": ttl,
        "expires_at": expires_at,
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
            "detail": {"run_id": run_id, "resource_class": resource_class, "expires_at": expires_at},
        },
    )
    return True, lease_path, lease_record


def _renew_resource_leases_for_wo(project_root: Path, wo_id: str) -> list[dict[str, Any]]:
    """Extend every held lease owned by *wo_id* by one TTL from now."""
    leases_dir = project_root / ".pkde" / "control" / "leases"
    renewed: list[dict[str, Any]] = []
    if not leases_dir.is_dir():
        return renewed
    for lease_file in sorted(leases_dir.glob("*.json")):
        data = json.loads(lease_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("state") not in ("held", "active"):
            continue
        if (data.get("work_order_id") or data.get("holder_wo_id")) != wo_id:
            continue
        ttl = int(data.get("ttl_minutes") or _lease_ttl_minutes())
        data["expires_at"] = (
            datetime.now(timezone.utc) + timedelta(minutes=ttl)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        data["extensions"] = int(data.get("extensions", 0)) + 1
        lease_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        controlstore.append_event(
            project_root,
            {
                "type": "lease.renewed",
                "subject_id": str(data.get("resource") or lease_file.stem),
                "actor": wo_id,
                "detail": {"expires_at": data["expires_at"], "extensions": data["extensions"]},
            },
        )
        renewed.append(
            {
                "resource": data.get("resource") or lease_file.stem,
                "expires_at": data["expires_at"],
                "extensions": data["extensions"],
            }
        )
    return renewed


def _release_resource_leases_for_wo(project_root: Path, wo_id: str) -> list[str]:
    """Release any active resource leases held by *wo_id*."""
    leases_dir = project_root / ".pkde" / "control" / "leases"
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


def _write_unique_spec_yaml(
    project_root: Path,
    normalized: dict[str, Any],
) -> Path:
    """Write normalized WO spec to a microsecond+counter unique YAML file."""
    global _SPEC_SEQ
    _SPEC_SEQ += 1
    role = normalized["requested_role"]
    specs_dir = project_root / ".pkde" / "control" / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    yaml_path = specs_dir / f"wo-spec-{ts}-{_SPEC_SEQ:03d}-{role}.yaml"
    spec_text = (
        yaml.safe_dump(normalized, sort_keys=False)
        if yaml is not None
        else json.dumps(normalized, indent=2) + "\n"
    )
    yaml_path.write_text(spec_text, encoding="utf-8")
    return yaml_path


def _build_specialist_brief(
    project_root: Path,
    wo_id: str,
    revision: int,
    run_id: str | None,
    normalized: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Build the Markdown specialist brief and ready-to-call invoke_subagent payload."""
    role = normalized["requested_role"]
    layer_0_req = (
        normalized["deliverables"].get("layer_0")
        or normalized["deliverables"].get("layer_0_classes")
        or normalized["deliverables"].get("required_classes")
        or []
    )
    layer_1_req = normalized["deliverables"].get("layer_1") or []
    rel_wo_record = f".pkde/control/work-orders/{wo_id}-r{revision}.json"
    rel_snapshot = f".pkde/control/contexts/{wo_id}-r{revision}.json"
    run_label = run_id or "QUEUED"
    agent_slug = f"pkde-{role}-{wo_id.lower()}"
    resolved_proj = project_root.resolve()
    resolved_repo = REPO_ROOT.resolve()
    if resolved_proj == resolved_repo:
        display_proj = "."
    elif resolved_proj.is_relative_to(resolved_repo):
        display_proj = str(resolved_proj.relative_to(resolved_repo))
    else:
        display_proj = str(project_root)

    specialist_brief = (
        f"# WORK ORDER DISPATCH: {wo_id} (Revision {revision} | Run {run_label})\n"
        f"- **Assigned Role**: `{role}` (Subagent: `pkde-{role}` | Slug: `{agent_slug}`)\n"
        f"- **Stage / Cycle**: Stage {normalized['stage']}, Cycle {normalized['cycle']}\n"
        f"- **Workspace Root**: `{display_proj}`\n"
        f"- **Work Order Record**: `{rel_wo_record}`\n"
        f"- **Context Snapshot**: `{rel_snapshot}`\n\n"
        f"## Environment & Attribution Setup (Run First)\n"
        f"```bash\n"
        f"source \"./bin/env.sh\"\n"
        f"export PKDE_PROJECT=\"{display_proj}\"\n"
        f"export PKDE_WORK_ORDER_ID=\"{wo_id}\"\n"
        f"export PKDE_RUN_ID=\"{run_label}\"\n"
        f"export PKDE_AGENT_ROLE=\"{role}\"\n"
        f"export PKDE_AGENT_SLUG=\"{agent_slug}\"\n"
        f"```\n\n"
        f"## Decision Question\n{normalized['decision_question']}\n\n"
        f"## Context\n{normalized['context'].get('content', '')}\n\n"
        f"## Required Deliverables\n"
        f"- **Layer 0 Artifact Classes**: `{json.dumps(layer_0_req)}`\n"
        f"- **Layer 1 Findings Reports**: `{json.dumps(layer_1_req)}`\n\n"
        f"## Mandatory Execution Rules\n"
        f"1. Export the `PKDE_*` environment variables above in every shell invocation so all sidecars and telemetry events carry `work_order_id: \"{wo_id}\"`.\n"
        f"2. Run both Phase 1 (`fetch`/`run`/`compute`/`predict`) and Phase 2 (`analyze`) for every domain tool.\n"
        f"3. Every Layer 1 finding report MUST include `## Summary`, `## Verdict`, and `## Evidence` headings, "
        f"cite `{wo_id}` (or `r{revision}`), include inline `{{source: raw/...}}` tags for quantitative claims, "
        f"and surface every `mandatory_relays` code from `.analysis.json` as `**Relay: \\`<code>\\`**`.\n"
        f"4. Run `./bin/pkde validate check {wo_id} --dry-run` before finishing to verify all 10 checks pass.\n"
        + (
            "5. This is a `synthesis_only` work order: cite upstream work orders' Layer 0 artifacts "
            "with `{source: raw/...}` tags; do not hand-write new raw/ files.\n"
            if normalized["deliverables"].get("synthesis_only") is True
            else ""
        )
        + (
            f"6. You hold the exclusive `{normalized['resource_class']}` lease (TTL-bound). For long jobs, renew it with "
            f"`./bin/pkde workorder renew-lease {wo_id} --json` before it expires.\n"
            if normalized.get("resource_class", "standard") != "standard"
            else ""
        )
    )
    role_title = role.replace("-", " ").title()
    subagent_invocation = {
        "TypeName": f"pkde-{role}",
        "Role": f"{role_title} ({wo_id})",
        "Prompt": specialist_brief,
        "Model": "inherit",
        "Workspace": "inherit",
    }
    return specialist_brief, subagent_invocation


def _start_queued_workorder(
    project_root: Path,
    wo_id: str,
    revision: int,
    normalized: dict[str, Any],
) -> dict[str, Any]:
    """Transition a committed/queued WO to in_progress, start its run, and acquire its lease.

    Every control-plane transition is checked; the first failure is returned
    as ``TRANSITION_FAILED`` with the failing command and CLI error.
    """
    role = normalized["requested_role"]
    resource_class = normalized["resource_class"]

    try:
        wo_rec = controlstore.read_record(project_root, "work-order", f"{wo_id}-r{revision}")
        if wo_rec.get("state") == "committed":
            _exec_checked(f"workorder transition {wo_id} queued --json", project_root, "wo_queue")
        _exec_checked(
            f"workorder transition {wo_id} in_progress --json", project_root, "wo_start"
        )
    except _ControlPlaneError as exc:
        return exc.as_result(work_order_id=wo_id, revision=revision)

    run_res = pkde_exec(
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
    try:
        _exec_checked(f"run transition {run_id} starting --json", project_root, "run_starting")
        _exec_checked(f"run transition {run_id} running --json", project_root, "run_running")
    except _ControlPlaneError as exc:
        return exc.as_result(work_order_id=wo_id, revision=revision, run_id=run_id)

    acquired, lease_path, lease_record = _acquire_resource_lease(
        project_root, resource_class, wo_id, revision, run_id, role
    )
    if not acquired:
        detail = f"resource lease '{resource_class}' unavailable at run start"
        fail_res = pkde_exec(
            f"run transition {run_id} failed --failure-class contract_failure "
            f"--detail {shlex.quote(detail)} --json",
            project_dir=str(project_root),
            auto_refresh_dashboard=False,
        )
        return {
            "ok": False,
            "status": "RESOURCE_BUSY",
            "work_order_id": wo_id,
            "revision": revision,
            "run_id": run_id,
            "resource_class": resource_class,
            "lease_holder": lease_record,
            "run_marked_failed": bool(fail_res.get("ok")),
        }

    snapshot_path = (
        project_root / ".pkde" / "control" / "contexts" / f"{wo_id}-r{revision}.json"
    )
    wo_record_path = (
        project_root / ".pkde" / "control" / "work-orders" / f"{wo_id}-r{revision}.json"
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
                "subagent_name": f"pkde-{role}",
                "run_id": run_id,
                "decision_question": normalized["decision_question"],
            },
        },
    )

    specialist_brief, subagent_invocation = _build_specialist_brief(
        project_root, wo_id, revision, run_id, normalized
    )

    return {
        "ok": True,
        "status": "DISPATCHED",
        "work_order_id": wo_id,
        "revision": revision,
        "run_id": run_id,
        "requested_role": role,
        "subagent_name": f"pkde-{role}",
        "agent_slug": f"pkde-{role}-{wo_id.lower()}",
        "resource_class": resource_class,
        "dependencies": list(normalized.get("dependencies", [])),
        "lease": lease_record,
        "lease_path": str(lease_path) if lease_path else None,
        "context_snapshot_path": str(snapshot_path),
        "work_order_record_path": str(wo_record_path),
        "specialist_brief": specialist_brief,
        "subagent_invocation": subagent_invocation,
    }


def pkde_dispatch_workorder(
    spec: dict[str, Any] | list[dict[str, Any]],
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Execute the 4-step Work Order intake ceremony and prepare a specialist brief.

    If ``spec`` is a list of work-order specs (or a dict containing ``"work_orders": [...]``),
    automatically delegates to ``pkde_dispatch_cohort`` for multi-persona wave dispatch.
    """
    if isinstance(spec, list):
        return pkde_dispatch_cohort(specs=spec, project_dir=project_dir)
    if isinstance(spec, dict) and isinstance(spec.get("work_orders"), list):
        return pkde_dispatch_cohort(specs=spec["work_orders"], project_dir=project_dir)

    project_root = resolve_project_root(project_dir)
    try:
        normalized = _normalize_workorder_spec(spec)
    except WorkOrderSpecError as exc:
        return {
            "ok": False,
            "status": "INVALID_SPEC",
            "errors": exc.errors,
            "remedy": "fix the listed fields; no work order was created",
        }
    role = normalized["requested_role"]
    resource_class = normalized["resource_class"]

    # Check if resource lease is busy before creating/starting a run
    busy, existing_lease = _is_resource_lease_busy(project_root, resource_class)
    if busy and existing_lease is not None:
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
                "Wait for that work order to validate/complete before dispatching, "
                "or use pkde_dispatch_cohort to queue it for Wave 2."
            ),
        }

    yaml_path = _write_unique_spec_yaml(project_root, normalized)

    # Step 1 & 2: Create and commit Work Order (creates context snapshot)
    create_res = pkde_exec(
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

    started = _start_queued_workorder(project_root, wo_id, revision, normalized)
    if not started.get("ok"):
        return started

    dashboard_path, _ = _safe_build_dashboard(project_root)
    started["dashboard_html"] = dashboard_path
    return started


def _latest_wo_records_by_id(project_root: Path) -> dict[str, dict[str, Any]]:
    records = controlstore.list_records(project_root, "work-order")
    by_id: dict[str, dict[str, Any]] = {}
    for r in records:
        wid = str(r.get("id") or "")
        if not wid:
            continue
        if wid not in by_id or int(r.get("revision", 0)) >= int(by_id[wid].get("revision", 0)):
            by_id[wid] = r
    return by_id


def _are_dependencies_satisfied(
    deps: list[str],
    latest_wos: dict[str, dict[str, Any]],
) -> tuple[bool, list[str]]:
    """Return (all_satisfied, unsatisfied_ids)."""
    unsatisfied: list[str] = []
    satisfied_states = {
        "mechanically_validated",
        "scientifically_accepted",
        "under_scientific_review",
    }
    for dep in deps:
        dep_rec = latest_wos.get(dep)
        if dep_rec is None or dep_rec.get("state") not in satisfied_states:
            unsatisfied.append(dep)
    return len(unsatisfied) == 0, unsatisfied


def pkde_dispatch_cohort(
    specs: list[dict[str, Any]],
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Dispatch a multi-persona cohort of Work Orders with dependency and resource-lease wave scheduling.

    - Creates and commits all Work Orders in the cohort so every WO gets a canonical ``WO-NNN`` ID
      and frozen context snapshot.
    - Resolves intra-cohort dependency aliases (e.g. ``id_alias``, ``slug``, or role names) to
      their assigned ``WO-NNN`` IDs.
    - Wave 1 work orders (no unmet dependencies and no resource lease conflict) are immediately
      transitioned to ``in_progress`` with active ``running`` runs and ready-to-call
      ``subagent_invocations`` for ``invoke_subagent(Subagents=...)``.
    - Wave 2+ work orders (waiting on upstream dependencies or exclusive resource leases) are
      placed in ``queued`` state and automatically promoted when ``pkde_validate_and_gate`` or
      ``pkde_manage_cohort(action="advance_wave")`` completes their prerequisites.
    """
    project_root = resolve_project_root(project_dir)
    if not isinstance(specs, list) or not specs:
        return {
            "ok": False,
            "status": "EMPTY_COHORT",
            "error": "pkde_dispatch_cohort requires a non-empty list of work-order specs",
        }

    latest_wos = _latest_wo_records_by_id(project_root)

    # Pre-validate the whole cohort before creating anything, so a bad spec
    # or a dangling dependency cannot leave a half-dispatched cohort or a
    # work order queued forever on an alias that never resolves.
    spec_errors: list[dict[str, Any]] = []
    normalized_specs: list[tuple[str, dict[str, Any]]] = []
    known_aliases: set[str] = set()
    for idx, raw_spec in enumerate(specs):
        if not isinstance(raw_spec, dict):
            spec_errors.append({"spec_index": idx, "errors": ["spec must be a mapping"]})
            continue
        alias = str(
            raw_spec.get("spec_id")
            or raw_spec.get("id_alias")
            or raw_spec.get("alias")
            or raw_spec.get("slug")
            or f"spec-{idx}"
        ).strip()
        try:
            normalized_i = _normalize_workorder_spec(dict(raw_spec))
        except WorkOrderSpecError as exc:
            spec_errors.append({"spec_index": idx, "spec_id": alias, "errors": exc.errors})
            continue
        dep_errors = [
            f"depends_on '{d}' does not match an earlier spec_id/role in this cohort "
            "or an existing work order"
            for d in (str(x).strip() for x in normalized_i.get("dependencies", []))
            if d not in known_aliases and d not in latest_wos
        ]
        if dep_errors:
            spec_errors.append({"spec_index": idx, "spec_id": alias, "errors": dep_errors})
        role_i = normalized_i["requested_role"]
        known_aliases.update({alias, str(idx), role_i, f"pkde-{role_i}"})
        normalized_specs.append((alias, normalized_i))
    if spec_errors:
        return {
            "ok": False,
            "status": "INVALID_SPEC",
            "spec_errors": spec_errors,
            "remedy": "fix the listed specs; no work orders were created",
        }

    alias_to_wo_id: dict[str, str] = {}
    wo_wave_by_id: dict[str, int] = {}
    claimed_wave1_resources: set[str] = set()

    dispatched: list[dict[str, Any]] = []
    queued: list[dict[str, Any]] = []
    waves_map: dict[int, list[dict[str, Any]]] = {}

    for idx, (alias, normalized) in enumerate(normalized_specs):
        role = normalized["requested_role"]
        resource_class = normalized["resource_class"]

        # Resolve any intra-cohort dependency aliases to real WO-NNN IDs
        resolved_deps: list[str] = []
        for dep in normalized.get("dependencies", []):
            dep_str = str(dep).strip()
            if dep_str in alias_to_wo_id:
                resolved_deps.append(alias_to_wo_id[dep_str])
            else:
                resolved_deps.append(dep_str)
        normalized["dependencies"] = resolved_deps

        yaml_path = _write_unique_spec_yaml(project_root, normalized)
        create_res = pkde_exec(
            f"workorder create --from {shlex.quote(str(yaml_path))} --commit --json",
            project_dir=str(project_root),
            auto_refresh_dashboard=False,
        )
        if not create_res["ok"] or not isinstance(create_res["data"], dict):
            return {
                "ok": False,
                "status": "CREATE_FAILED",
                "failed_spec_index": idx,
                "error": create_res.get("stderr") or create_res.get("data"),
            }

        wo_data = create_res["data"]
        wo_id = str(wo_data["id"])
        revision = int(wo_data.get("revision", 1))

        alias_to_wo_id[alias] = wo_id
        alias_to_wo_id[str(idx)] = wo_id
        if role not in alias_to_wo_id:
            alias_to_wo_id[role] = wo_id
            alias_to_wo_id[f"pkde-{role}"] = wo_id

        # Refresh latest_wos map with the newly committed record
        latest_wos[wo_id] = controlstore.read_record(
            project_root, "work-order", f"{wo_id}-r{revision}"
        )

        deps_ok, unmet_deps = _are_dependencies_satisfied(resolved_deps, latest_wos)
        lease_busy_on_disk, _ = _is_resource_lease_busy(project_root, resource_class)
        lease_conflict = (
            resource_class != "standard"
            and (lease_busy_on_disk or resource_class in claimed_wave1_resources)
        )

        if deps_ok and not lease_conflict:
            wave_num = 1
            if resource_class != "standard":
                claimed_wave1_resources.add(resource_class)
            wo_wave_by_id[wo_id] = wave_num

            started = _start_queued_workorder(project_root, wo_id, revision, normalized)
            if not started.get("ok"):
                return started
            started["wave"] = wave_num
            dispatched.append(started)
            waves_map.setdefault(wave_num, []).append(started)
            latest_wos[wo_id] = controlstore.read_record(
                project_root, "work-order", f"{wo_id}-r{revision}"
            )
        else:
            # Determine wave number (max wave of dependencies + 1, or 2 for lease contention)
            dep_waves = [wo_wave_by_id.get(d, 1) for d in unmet_deps]
            wave_num = max(dep_waves, default=1) + 1
            wo_wave_by_id[wo_id] = wave_num

            try:
                _exec_checked(
                    f"workorder transition {wo_id} queued --json", project_root, "wo_queue"
                )
            except _ControlPlaneError as exc:
                return exc.as_result(
                    work_order_id=wo_id,
                    revision=revision,
                    dispatched_so_far=[d["work_order_id"] for d in dispatched],
                )
            wo_identifier = f"{wo_id}-r{revision}"
            wo_rec = controlstore.read_record(project_root, "work-order", wo_identifier)
            wo_rec["wave"] = wave_num
            wo_rec["blocked_by"] = unmet_deps + (
                [f"lease:{resource_class}"] if lease_conflict else []
            )
            controlstore.write_record(project_root, "work-order", wo_identifier, wo_rec)
            latest_wos[wo_id] = wo_rec

            brief_preview, inv_preview = _build_specialist_brief(
                project_root, wo_id, revision, None, normalized
            )
            queued_entry = {
                "ok": True,
                "status": "QUEUED_FOR_WAVE",
                "wave": wave_num,
                "work_order_id": wo_id,
                "revision": revision,
                "run_id": None,
                "requested_role": role,
                "subagent_name": f"pkde-{role}",
                "agent_slug": f"pkde-{role}-{wo_id.lower()}",
                "resource_class": resource_class,
                "dependencies": resolved_deps,
                "blocked_by": wo_rec["blocked_by"],
                "specialist_brief": brief_preview,
                "subagent_invocation": inv_preview,
            }
            queued.append(queued_entry)
            waves_map.setdefault(wave_num, []).append(queued_entry)

    dashboard_path, _ = _safe_build_dashboard(project_root)
    waves_list = [waves_map[w] for w in sorted(waves_map)]
    wave1_invocations = [d["subagent_invocation"] for d in dispatched]

    return {
        "ok": True,
        "status": "COHORT_DISPATCHED",
        "project_dir": str(project_root),
        "cohort_size": len(specs),
        "total_work_orders": len(specs),
        "dispatched_count": len(dispatched),
        "queued_count": len(queued),
        "wave_1_started": [d["work_order_id"] for d in dispatched],
        "wave_2_plus_queued": [q["work_order_id"] for q in queued],
        "dispatched_work_orders": dispatched,
        "queued_work_orders": queued,
        "waves": waves_list,
        "subagent_invocations": wave1_invocations,
        "dashboard_html": dashboard_path,
    }


def _advance_queued_wave(
    project_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Promote any 'queued' WOs whose dependencies and resource leases are now satisfied.

    Returns ``(promoted, failed)``; a promotion that fails a control-plane
    transition is reported in ``failed`` instead of being dropped.
    """
    latest_wos = _latest_wo_records_by_id(project_root)
    promoted: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    queued_wos = sorted(
        (r for r in latest_wos.values() if r.get("state") == "queued"),
        key=lambda r: (int(r.get("wave", 2)), str(r.get("id", ""))),
    )
    for wo_rec in queued_wos:
        wo_id = str(wo_rec["id"])
        revision = int(wo_rec.get("revision", 1))
        deps = list(wo_rec.get("dependencies") or [])
        resource_class = str(wo_rec.get("resource_class") or "standard")

        deps_ok, _ = _are_dependencies_satisfied(deps, latest_wos)
        if not deps_ok:
            continue
        busy, _ = _is_resource_lease_busy(project_root, resource_class, exclude_wo_id=wo_id)
        if busy:
            continue

        # Record was validated at dispatch; rebuild the brief without re-gating.
        normalized = _normalize_workorder_spec(wo_rec, strict=False)
        started = _start_queued_workorder(project_root, wo_id, revision, normalized)
        if started.get("ok"):
            started["wave"] = int(wo_rec.get("wave", 2))
            promoted.append(started)
            latest_wos[wo_id] = controlstore.read_record(
                project_root, "work-order", f"{wo_id}-r{revision}"
            )
        else:
            failed.append(started)
    return promoted, failed


def pkde_manage_cohort(
    action: str = "status",
    work_order_ids: list[str] | str | None = None,
    subagent_bindings: dict[str, str] | str | None = None,
    project_dir: str | None = None,
    work_order_id: str | None = None,
    subagent_id: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Manage a multi-persona cohort of Work Orders and active subagents.

    Supported actions:
    - ``"status"``: Inspect all work orders, runs, bound subagent ``conversation_id``s,
      deliverables readiness, and resource leases across the cohort.
    - ``"bind_subagent"``: Record live subagent ``conversation_id``s (returned by
      ``invoke_subagent``) onto their corresponding ``WO-NNN`` and ``RUN-NNN`` records.
    - ``"advance_wave"``: Promote any ``queued`` Wave 2+ work orders whose dependencies
      and resource leases are now satisfied, returning new ``subagent_invocations``.
    - ``"validate_cohort"``: Run the 10-check validation gate across all specified
      (or all ready-to-validate) work orders in the cohort and auto-advance the next wave.
    """
    project_root = resolve_project_root(project_dir)
    act = str(action or "status").strip().lower()

    if work_order_id and not work_order_ids:
        work_order_ids = [work_order_id]

    parsed_wo_ids: list[str] = []
    if isinstance(work_order_ids, str) and work_order_ids.strip():
        raw_ids = work_order_ids.strip()
        if raw_ids.startswith("["):
            try:
                parsed_wo_ids = [str(x).strip() for x in json.loads(raw_ids) if str(x).strip()]
            except ValueError:
                parsed_wo_ids = [x.strip() for x in raw_ids.split(",") if x.strip()]
        elif raw_ids.lower() != "all":
            parsed_wo_ids = [x.strip() for x in raw_ids.split(",") if x.strip()]
    elif isinstance(work_order_ids, list):
        parsed_wo_ids = [str(x).strip() for x in work_order_ids if str(x).strip()]

    parsed_bindings: dict[str, str] = {}
    if isinstance(subagent_bindings, dict):
        parsed_bindings = {str(k).strip(): str(v).strip() for k, v in subagent_bindings.items()}
    elif isinstance(subagent_bindings, str) and subagent_bindings.strip():
        raw_b = subagent_bindings.strip()
        if raw_b.startswith("{"):
            try:
                loaded_b = json.loads(raw_b)
            except ValueError as exc:
                return {
                    "ok": False,
                    "status": "INVALID_BINDINGS",
                    "error": f"subagent_bindings is not valid JSON: {exc}",
                }
            if not isinstance(loaded_b, dict):
                return {
                    "ok": False,
                    "status": "INVALID_BINDINGS",
                    "error": "subagent_bindings JSON must be an object {\"WO-NNN\": \"<conversation_id>\"}",
                }
            parsed_bindings = {str(k).strip(): str(v).strip() for k, v in loaded_b.items()}
        elif len(parsed_wo_ids) == 1:
            parsed_bindings = {parsed_wo_ids[0]: raw_b}
    if work_order_id and subagent_id:
        parsed_bindings[str(work_order_id).strip()] = str(subagent_id).strip()
    elif len(parsed_wo_ids) == 1 and subagent_id:
        parsed_bindings[parsed_wo_ids[0]] = str(subagent_id).strip()

    if act == "renew_lease":
        if not parsed_wo_ids:
            return {
                "ok": False,
                "status": "MISSING_WORK_ORDER",
                "error": "renew_lease requires work_order_id",
            }
        renewed = {wid: _renew_resource_leases_for_wo(project_root, wid) for wid in parsed_wo_ids}
        any_renewed = any(renewed.values())
        return {
            "ok": any_renewed,
            "status": "LEASE_RENEWED" if any_renewed else "NO_HELD_LEASE",
            "renewed": renewed,
        }

    if act == "bind_subagent":
        if not parsed_bindings:
            return {
                "ok": False,
                "status": "NO_BINDINGS",
                "error": "bind_subagent requires work_order_id + subagent_id or subagent_bindings",
            }
        if run_id and len(parsed_bindings) != 1:
            return {
                "ok": False,
                "status": "AMBIGUOUS_RUN_ID",
                "error": "an explicit run_id can only be bound together with a single work order",
            }
        latest_wos = _latest_wo_records_by_id(project_root)
        bound_records: list[dict[str, Any]] = []
        unmatched: list[dict[str, str]] = []
        for wid, conv_id in parsed_bindings.items():
            wo_rec = latest_wos.get(wid)
            if wo_rec is None:
                unmatched.append({"work_order_id": wid, "reason": "work order not found"})
                continue
            rev = int(wo_rec.get("revision", 1))
            wo_ident = f"{wid}-r{rev}"

            runs = controlstore.list_records(
                project_root,
                "run",
                lambda r, _w=wid, _rv=rev: (
                    r.get("work_order_id") == _w and r.get("work_order_revision") == _rv
                ),
            )
            target_run: dict[str, Any] | None = None
            if run_id:
                target_run = next(
                    (r for r in runs if str(r.get("run_id") or r.get("id")) == run_id), None
                )
                if target_run is None:
                    unmatched.append(
                        {
                            "work_order_id": wid,
                            "reason": f"run {run_id} does not belong to {wid}-r{rev}",
                        }
                    )
                    continue
            elif runs:
                target_run = max(runs, key=lambda r: str(r.get("created_at", "")))

            wo_rec["subagent_id"] = conv_id
            wo_rec["conversation_id"] = conv_id
            controlstore.write_record(project_root, "work-order", wo_ident, wo_rec)

            run_id_bound: str | None = None
            if target_run is not None:
                run_id_bound = str(target_run.get("run_id") or target_run.get("id"))
                target_run["subagent_id"] = conv_id
                target_run["conversation_id"] = conv_id
                controlstore.write_record(project_root, "run", run_id_bound, target_run)

            role = str(wo_rec.get("requested_role") or "specialist")
            controlstore.append_event(
                project_root,
                {
                    "type": "subagent.spawned",
                    "subject_id": wid,
                    "revision": rev,
                    "actor": f"pkde-{role}",
                    "detail": {
                        "work_order_id": wid,
                        "run_id": run_id_bound,
                        "requested_role": role,
                        "subagent_name": f"pkde-{role}",
                        "subagent_id": conv_id,
                        "conversation_id": conv_id,
                    },
                },
            )
            bound_records.append(
                {
                    "work_order_id": wid,
                    "revision": rev,
                    "run_id": run_id_bound,
                    "requested_role": role,
                    "subagent_id": conv_id,
                }
            )
        dashboard_path, _ = _safe_build_dashboard(project_root)
        all_bound = bool(bound_records) and not unmatched
        return {
            "ok": all_bound,
            "status": (
                "SUBAGENTS_BOUND"
                if all_bound
                else ("PARTIALLY_BOUND" if bound_records else "NO_MATCHING_WORK_ORDERS")
            ),
            "bound_count": len(bound_records),
            "bound": bound_records,
            "unmatched": unmatched,
            "dashboard_html": dashboard_path,
        }

    if act == "advance_wave":
        promoted, promotion_failures = _advance_queued_wave(project_root)
        dashboard_path, _ = _safe_build_dashboard(project_root)
        return {
            "ok": not promotion_failures,
            "status": (
                "PROMOTION_FAILED"
                if promotion_failures
                else ("WAVE_ADVANCED" if promoted else "NO_ELIGIBLE_QUEUED_WORK_ORDERS")
            ),
            "promoted_count": len(promoted),
            "promoted": promoted,
            "promotion_failures": promotion_failures,
            "dispatched_work_orders": promoted,
            "subagent_invocations": [p["subagent_invocation"] for p in promoted],
            "dashboard_html": dashboard_path,
        }

    if act == "validate_cohort":
        latest_wos = _latest_wo_records_by_id(project_root)
        target_ids = parsed_wo_ids or [
            wid
            for wid, rec in sorted(latest_wos.items())
            if rec.get("state") in ("in_progress", "submitted", "validation_failed")
        ]
        results: list[dict[str, Any]] = []
        for wid in target_ids:
            res = pkde_validate_and_gate(
                work_order_id=wid,
                project_dir=str(project_root),
                auto_advance_wave=False,
            )
            results.append(res)
        promoted, promotion_failures = _advance_queued_wave(project_root)
        dashboard_path, _ = _safe_build_dashboard(project_root)
        all_ok = bool(results) and all(r.get("ok") for r in results) and not promotion_failures
        next_invocations = [p["subagent_invocation"] for p in promoted]
        return {
            "ok": all_ok,
            "status": "COHORT_VALIDATED" if all_ok else "COHORT_VALIDATION_INCOMPLETE",
            "validated_count": sum(1 for r in results if r.get("ok")),
            "total_checked": len(results),
            "results": results,
            "promoted_wave": {
                "promoted_count": len(promoted),
                "promoted": promoted,
                "promotion_failures": promotion_failures,
                "subagent_invocations": next_invocations,
            },
            "unblocked_work_orders": promoted,
            "next_wave_subagent_invocations": next_invocations,
            "dashboard_html": dashboard_path,
        }

    # Default: action == "status"
    latest_wos = _latest_wo_records_by_id(project_root)
    all_runs = controlstore.list_records(project_root, "run")
    items: list[dict[str, Any]] = []
    by_state: dict[str, int] = {}

    for wid in sorted(latest_wos):
        if parsed_wo_ids and wid not in parsed_wo_ids:
            continue
        rec = latest_wos[wid]
        rev = int(rec.get("revision", 1))
        st = str(rec.get("state") or "unknown")
        by_state[st] = by_state.get(st, 0) + 1
        matching_runs = [
            r
            for r in all_runs
            if r.get("work_order_id") == wid and int(r.get("work_order_revision", 1)) == rev
        ]
        latest_run = (
            max(matching_runs, key=lambda r: str(r.get("created_at", "")))
            if matching_runs
            else {}
        )
        layer_1_paths = (rec.get("deliverables") or {}).get("layer_1") or []
        l1_ready = bool(layer_1_paths) and all(
            (project_root / p).is_file() for p in layer_1_paths
        )
        items.append(
            {
                "work_order_id": wid,
                "revision": rev,
                "state": st,
                "wave": rec.get("wave", 1),
                "requested_role": rec.get("requested_role"),
                "subagent_name": f"pkde-{rec.get('requested_role', 'specialist')}",
                "run_id": latest_run.get("run_id") or latest_run.get("id"),
                "run_state": latest_run.get("state"),
                "subagent_id": rec.get("subagent_id") or latest_run.get("subagent_id"),
                "dependencies": rec.get("dependencies", []),
                "resource_class": rec.get("resource_class", "standard"),
                "layer_1_deliverables_present": l1_ready,
            }
        )

    return {
        "ok": True,
        "status": "COHORT_STATUS",
        "project_dir": str(project_root),
        "total_work_orders": len(items),
        "counts_by_state": by_state,
        "work_orders": items,
    }


def pkde_validate_and_gate(
    work_order_id: str,
    run_id: str | None = None,
    project_dir: str | None = None,
    auto_advance_wave: bool = True,
) -> dict[str, Any]:
    """Run the 10-check mechanical validation gate and drive the correction loop.

    Supports validating a single ``WO-NNN``, comma-separated IDs (``"WO-001,WO-002"``),
    or ``"all"`` active work orders in the cohort.
    """
    clean_id = str(work_order_id or "").strip()
    if clean_id.lower() == "all" or "," in clean_id:
        wo_list = (
            None
            if clean_id.lower() == "all"
            else [x.strip() for x in clean_id.split(",") if x.strip()]
        )
        return pkde_manage_cohort(
            action="validate_cohort",
            work_order_ids=wo_list,
            project_dir=project_dir,
        )

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

    # Already past the mechanical gate -> nothing to re-validate.
    if wo_state in ("mechanically_validated", "under_scientific_review", "scientifically_accepted"):
        return {
            "ok": True,
            "status": "ALREADY_VALIDATED",
            "work_order_id": work_order_id,
            "revision": revision,
            "state": wo_state,
        }

    # Bring work order to 'submitted' state if needed (each hop checked).
    try:
        if wo_state == "committed":
            _exec_checked(
                f"workorder transition {work_order_id} queued --json", project_root, "wo_queue"
            )
            wo_state = "queued"
        if wo_state in ("queued", "validation_failed"):
            _exec_checked(
                f"workorder transition {work_order_id} in_progress --json",
                project_root,
                "wo_start",
            )
            wo_state = "in_progress"
        if wo_state == "in_progress":
            _exec_checked(
                f"workorder transition {work_order_id} submitted --json",
                project_root,
                "wo_submit",
            )
            wo_state = "submitted"
    except _ControlPlaneError as exc:
        return exc.as_result(work_order_id=work_order_id, revision=revision, run_id=run_id)
    if wo_state != "submitted":
        return {
            "ok": False,
            "status": "INVALID_STATE",
            "work_order_id": work_order_id,
            "revision": revision,
            "state": wo_state,
            "error": f"work order is in state {wo_state!r}; it cannot be submitted for validation",
        }

    # Run the 10-check validator
    val_res = pkde_exec(
        f"validate check {work_order_id} --revision {revision} --json",
        project_dir=str(project_root),
        auto_refresh_dashboard=False,
    )
    val_data = val_res.get("data") if isinstance(val_res.get("data"), dict) else {}
    if "result" not in val_data or not isinstance(val_data.get("checks"), list):
        # The validator itself errored (no check results) -- this is not a
        # specialist defect and must not consume a correction cycle.
        return {
            "ok": False,
            "status": "VALIDATOR_ERROR",
            "work_order_id": work_order_id,
            "revision": revision,
            "run_id": run_id,
            "exit_code": val_res.get("exit_code"),
            "error": val_res.get("stderr") or val_res.get("data"),
        }
    result = val_data["result"]
    checks = val_data["checks"]
    failed_checks = [c for c in checks if c.get("result") == "fail"]
    failed_names = [c.get("name", "") for c in failed_checks]

    # Case 1: Validation Passed
    if result in ("pass", "pass_with_warnings"):
        run_transition_errors: list[str] = []
        if run_id:
            try:
                run_rec = controlstore.read_record(project_root, "run", run_id)
                r_state = run_rec.get("state")
                if r_state == "queued":
                    _exec_checked(f"run transition {run_id} starting --json", project_root, "run_starting")
                    r_state = "starting"
                if r_state == "starting":
                    _exec_checked(f"run transition {run_id} running --json", project_root, "run_running")
                    r_state = "running"
                if r_state == "running":
                    _exec_checked(f"run transition {run_id} succeeded --json", project_root, "run_succeeded")
            except _ControlPlaneError as exc:
                run_transition_errors.append(str(exc))
            except Exception as exc:  # run record unreadable
                run_transition_errors.append(f"run {run_id}: {type(exc).__name__}: {exc}")
        else:
            run_transition_errors.append("no run record found for this work order revision")

        released_leases = _release_resource_leases_for_wo(project_root, work_order_id)
        promoted, promotion_failures = (
            _advance_queued_wave(project_root) if auto_advance_wave else ([], [])
        )
        dashboard_path, _ = _safe_build_dashboard(project_root)

        out_payload: dict[str, Any] = {
            "ok": True,
            "status": "PASSED",
            "work_order_id": work_order_id,
            "revision": revision,
            "run_id": run_id,
            "validation_result": result,
            "checks": checks,
            "checks_failed": [],
            "released_leases": released_leases,
            "run_transition_errors": run_transition_errors,
            "ready_for_scientific_review": True,
            "dashboard_html": dashboard_path,
        }
        if promoted:
            out_payload["unblocked_work_orders"] = promoted
            out_payload["next_wave_subagent_invocations"] = [
                p["subagent_invocation"] for p in promoted
            ]
        if promotion_failures:
            out_payload["promotion_failures"] = promotion_failures
        return out_payload

    # Case 2: Data Integrity Failure -> Halt immediately, no retry allowed
    data_integrity_failures = [
        c for c in failed_checks if c.get("kind") == "DATA_INTEGRITY"
    ]
    if data_integrity_failures:
        detail_msg = "; ".join(
            f"{c.get('name')}: {c.get('detail')}" for c in data_integrity_failures
        )
        run_fail_error = _fail_run(project_root, run_id, detail_msg)

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
            "run_transition_errors": [run_fail_error] if run_fail_error else [],
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
        try:
            _exec_checked(
                f"workorder transition {work_order_id} in_progress --json",
                project_root,
                "wo_reopen_for_correction",
            )
        except _ControlPlaneError as exc:
            return exc.as_result(
                work_order_id=work_order_id,
                revision=revision,
                run_id=run_id,
                checks_failed=failed_names,
            )
        bullet_lines = [
            f"- **{c.get('name')}** (`{c.get('kind', 'MECHANICAL')}`): {c.get('detail', '')}"
            for c in failed_checks
        ]
        correction_prompt = (
            f"CORRECTION REQUIRED {work_order_id} (Revision {revision}, Cycle {correction_cycle}/2):\n"
            f"Mechanical validation (`pkde validate check {work_order_id}`) failed on the following check(s):\n"
            + "\n".join(bullet_lines)
            + "\n\nPlease fix these defects in-place in the workspace and verify with "
            f"`pkde validate check {work_order_id} --dry-run` before reporting completion."
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
    run_fail_error = _fail_run(project_root, run_id, detail_msg)

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
        "run_transition_errors": [run_fail_error] if run_fail_error else [],
        "escalation_message": detail_msg,
        "dashboard_html": dashboard_path,
    }


def _fail_run(project_root: Path, run_id: str | None, detail: str) -> str | None:
    """Transition a running run to ``failed``; return an error string on failure."""
    if not run_id:
        return "no run record found for this work order revision"
    try:
        run_rec = controlstore.read_record(project_root, "run", run_id)
    except Exception as exc:  # run record unreadable
        return f"run {run_id}: {type(exc).__name__}: {exc}"
    if run_rec.get("state") != "running":
        return None
    try:
        _exec_checked(
            f"run transition {run_id} failed --failure-class contract_failure "
            f"--detail {shlex.quote(detail[:240])} --json",
            project_root,
            "run_failed",
        )
    except _ControlPlaneError as exc:
        return str(exc)
    return None


def pkde_render_dashboard(
    project_dir: str | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Build the self-contained PkDE Interactive Scientific Dashboard HTML."""
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


def pkde_bootstrap_session(
    prompt: str,
    program_name: str | None = None,
    stage: int | None = None,
    project_dir: str | None = None,
    host: str = "0.0.0.0",
    port: int = 8765,
    start_server: bool = True,
    fresh: bool = False,
    target: str | None = None,
    indication: str | None = None,
    modality: str | None = None,
) -> dict[str, Any]:
    """Initialize a live PkDE discovery session from the user's prompt and ensure the dashboard server is running."""
    project_root = resolve_project_root(project_dir)
    return bootstrap_prompt_session(
        project_root,
        prompt=prompt,
        program_name=program_name,
        target=target,
        indication=indication,
        modality=modality,
        stage=stage,
        host=host,
        port=port,
        start_server=start_server,
        fresh=fresh,
    )


def pkde_log_agent_message(
    from_agent: str,
    to_agent: str,
    summary: str,
    work_order_id: str | None = None,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Record an explicit inter-agent communication event in the PkDE control plane and refresh the dashboard."""
    project_root = resolve_project_root(project_dir)
    ev = log_agent_message(
        project_root,
        from_agent=from_agent,
        to_agent=to_agent,
        summary=summary,
        work_order_id=work_order_id,
    )
    dashboard_path, _ = _safe_build_dashboard(project_root)
    return {
        "ok": True,
        "event": ev,
        "project_dir": str(project_root),
        "dashboard_html": dashboard_path,
    }

