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

"""Contract tests for the pharmakon-discovery-engine skill.

These guard the properties the skill promises an orchestrating agent:

- every ``./bin/pkde`` command quoted in SKILL.md resolves to a real CLI
  command and uses only options that command accepts;
- work-order specs are never silently defaulted (role, question, and
  evidence-bearing deliverables are required; unknown personas rejected);
- a report-only work order cannot pass the mechanical gate;
- control-plane transition failures are surfaced, not swallowed;
- exclusive leases expire and can be renewed;
- subagent binding honours an explicit run id and reports mismatches;
- the MCP / script surfaces accept the arguments SKILL.md documents.
"""

from __future__ import annotations

import inspect
import json
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

from pkde.cli import cli as pkde_cli
from pkde.commands.validate import _check_deliverables_schema
from pkde.core import controlstore
from pkde_plugin import mcp_server
from pkde_plugin import tool_bridge
from pkde_plugin.tool_bridge import (
    PKDE_AGENT_ROLES,
    pkde_bootstrap_session,
    pkde_dispatch_cohort,
    pkde_dispatch_workorder,
    pkde_exec,
    pkde_manage_cohort,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / ".agents" / "plugins" / "pharmakon-discovery-engine"
SKILL_COPIES = [
    REPO_ROOT / "SKILL.md",
    REPO_ROOT / "skills" / "pharmakon-discovery-engine" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "pharmakon-discovery-engine" / "SKILL.md",
]


def _good_spec(**overrides: object) -> dict:
    spec: dict = {
        "requested_role": "computational-biologist",
        "decision_question": "Is BRAF genetically constrained?",
        "deliverables": {
            "layer_0_classes": ["genomics"],
            "layer_1": ["findings/computational-biology/braf.md"],
        },
    }
    spec.update(overrides)
    return spec


def _work_orders(ws: Path) -> list[dict]:
    return controlstore.list_records(ws, "work-order")


# ---------------------------------------------------------------------------
# SKILL.md <-> CLI contract
# ---------------------------------------------------------------------------


def _skill_pkde_commands(text: str) -> list[str]:
    joined = re.sub(r"\\\s*\n\s*", " ", text)
    cmds = []
    for match in re.finditer(r"\./bin/pkde\s+([^`\n]+)", joined):
        cmd = match.group(1).split(" # ")[0].strip()
        if cmd and not cmd.startswith("<"):
            cmds.append(cmd)
    return cmds


def _option_names(cmd: click.Command) -> set[str]:
    names: set[str] = set()
    for param in cmd.params:
        if isinstance(param, click.Option):
            names.update(param.opts)
            names.update(param.secondary_opts)
    return names


def test_skill_md_copies_are_identical() -> None:
    texts = [p.read_text(encoding="utf-8") for p in SKILL_COPIES if p.is_file()]
    assert len(texts) == len(SKILL_COPIES), "a SKILL.md copy is missing"
    assert all(t == texts[0] for t in texts), "SKILL.md copies have diverged"


def test_every_skill_md_pkde_command_resolves_with_valid_options() -> None:
    text = SKILL_COPIES[0].read_text(encoding="utf-8")
    commands = _skill_pkde_commands(text)
    assert len(commands) >= 15, commands
    global_opts = _option_names(pkde_cli)
    problems: list[str] = []
    for raw in commands:
        tokens = [t.strip("[]") for t in shlex.split(raw)]
        tokens = [t for t in tokens if t]
        cmd: click.Command = pkde_cli
        path: list[str] = []
        idx = 0
        while isinstance(cmd, click.Group) and idx < len(tokens) and tokens[idx] in cmd.commands:
            cmd = cmd.commands[tokens[idx]]
            path.append(tokens[idx])
            idx += 1
        if isinstance(cmd, click.Group):
            problems.append(f"`pkde {raw}` does not resolve to a leaf command (stopped at {path})")
            continue
        valid = _option_names(cmd) | global_opts
        for tok in tokens[idx:]:
            if tok.startswith("--"):
                opt = tok.split("=", 1)[0]
                if opt not in valid:
                    problems.append(f"`pkde {' '.join(path)}` has no option {opt} (from: {raw})")
    assert not problems, "\n".join(problems)


# ---------------------------------------------------------------------------
# Persona registry
# ---------------------------------------------------------------------------


def test_role_registry_matches_agent_definitions() -> None:
    agent_roles = {
        p.stem.removeprefix("pkde-") for p in (PLUGIN_ROOT / "agents").glob("pkde-*.md")
    }
    assert agent_roles == set(PKDE_AGENT_ROLES)


# ---------------------------------------------------------------------------
# Strict spec validation (no silent defaults)
# ---------------------------------------------------------------------------


def test_dispatch_rejects_underspecified_specs_without_creating_work_orders(tmp_path: Path) -> None:
    ws = tmp_path / "ws-strict"
    bad_specs = {
        "missing role": {k: v for k, v in _good_spec().items() if k != "requested_role"},
        "unknown role": _good_spec(requested_role="pkde-medchem"),
        "missing question": {k: v for k, v in _good_spec().items() if k != "decision_question"},
        "blank question": _good_spec(decision_question="   "),
        "missing deliverables": {k: v for k, v in _good_spec().items() if k != "deliverables"},
        "report only": _good_spec(deliverables={"layer_1": ["findings/x/y.md"]}),
        "evidence only": _good_spec(deliverables={"layer_0_classes": ["genomics"]}),
    }
    for label, spec in bad_specs.items():
        res = pkde_dispatch_workorder(spec, project_dir=str(ws))
        assert res["ok"] is False, label
        assert res["status"] == "INVALID_SPEC", (label, res)
        assert res["errors"], label
    assert _work_orders(ws) == []


def test_synthesis_only_work_order_is_accepted_and_flagged_in_brief(tmp_path: Path) -> None:
    ws = tmp_path / "ws-synth"
    res = pkde_dispatch_workorder(
        _good_spec(
            requested_role="pkde-scientific-reviewer",
            decision_question="Does the BRAF genetics finding hold up on re-analysis?",
            deliverables={"synthesis_only": True, "layer_1": ["findings/reviews/braf-review.md"]},
        ),
        project_dir=str(ws),
    )
    assert res["ok"] is True, res
    assert res["subagent_invocation"]["TypeName"] == "pkde-scientific-reviewer"
    assert "synthesis_only" in res["specialist_brief"]


def test_cohort_is_validated_atomically_including_dependencies(tmp_path: Path) -> None:
    ws = tmp_path / "ws-cohort-strict"
    specs = [
        _good_spec(spec_id="genetics"),
        _good_spec(
            spec_id="review",
            requested_role="scientific-reviewer",
            depends_on=["genetcs"],  # typo: must not queue forever
            deliverables={"synthesis_only": True, "layer_1": ["findings/reviews/r.md"]},
        ),
        {"spec_id": "empty"},
    ]
    res = pkde_dispatch_cohort(specs=specs, project_dir=str(ws))
    assert res["ok"] is False
    assert res["status"] == "INVALID_SPEC"
    flagged = {e["spec_index"] for e in res["spec_errors"]}
    assert flagged == {1, 2}
    assert any("genetcs" in msg for e in res["spec_errors"] for msg in e["errors"])
    assert _work_orders(ws) == []


def test_validator_rejects_report_only_deliverables() -> None:
    fail = _check_deliverables_schema({"layer_1": ["findings/x/y.md"]})
    assert fail is not None and fail["result"] == "fail" and fail["kind"] == "COMPLETENESS"
    assert _check_deliverables_schema(
        {"layer_1": ["findings/x/y.md"], "synthesis_only": True}
    ) is None
    assert _check_deliverables_schema(
        {"layer_1": ["findings/x/y.md"], "layer_0_classes": ["genomics"]}
    ) is None


# ---------------------------------------------------------------------------
# Transition failures are surfaced
# ---------------------------------------------------------------------------


def test_failed_control_plane_transition_is_reported(tmp_path: Path) -> None:
    ws = tmp_path / "ws-transition"
    res = pkde_dispatch_workorder(_good_spec(), project_dir=str(ws))
    assert res["ok"] is True
    normalized = tool_bridge._normalize_workorder_spec(_good_spec())
    # WO is already in_progress -> in_progress->in_progress is illegal.
    again = tool_bridge._start_queued_workorder(
        ws, res["work_order_id"], res["revision"], normalized
    )
    assert again["ok"] is False
    assert again["status"] == "TRANSITION_FAILED"
    assert again["failed_step"] == "wo_start"
    assert "workorder transition" in again["command"]


# ---------------------------------------------------------------------------
# Lease TTL
# ---------------------------------------------------------------------------


def test_expired_lease_is_released_and_renewal_extends_ttl(tmp_path: Path) -> None:
    ws = tmp_path / "ws-lease"
    first = pkde_dispatch_workorder(_good_spec(resource_class="af3"), project_dir=str(ws))
    assert first["ok"] is True
    lease = first["lease"]
    granted = datetime.strptime(lease["granted_at"], "%Y-%m-%dT%H:%M:%SZ")
    expires = datetime.strptime(lease["expires_at"], "%Y-%m-%dT%H:%M:%SZ")
    assert (expires - granted).total_seconds() == lease["ttl_minutes"] * 60

    blocked = pkde_dispatch_workorder(
        _good_spec(resource_class="af3", requested_role="structural-biologist"),
        project_dir=str(ws),
    )
    assert blocked["status"] == "RESOURCE_BUSY"

    # Simulate the holder crashing: the lease's TTL lapses.
    lease_path = Path(first["lease_path"])
    stale = json.loads(lease_path.read_text(encoding="utf-8"))
    stale["expires_at"] = "2000-01-01T00:00:00Z"
    lease_path.write_text(json.dumps(stale), encoding="utf-8")

    second = pkde_dispatch_workorder(
        _good_spec(resource_class="af3", requested_role="structural-biologist"),
        project_dir=str(ws),
    )
    assert second["ok"] is True, second
    assert json.loads(lease_path.read_text(encoding="utf-8"))["work_order_id"] == second["work_order_id"]
    events = (ws / ".pkde" / "control" / "events.ndjson").read_text(encoding="utf-8")
    assert '"lease.expired"' in events

    renewed = pkde_exec(
        f"workorder renew-lease {second['work_order_id']} --json",
        project_dir=str(ws),
        auto_refresh_dashboard=False,
    )
    assert renewed["ok"] is True, renewed
    entry = renewed["data"]["renewed"][second["work_order_id"]][0]
    assert entry["extensions"] == 1
    assert datetime.strptime(entry["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    ) > datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Subagent binding
# ---------------------------------------------------------------------------


def test_bind_subagent_honours_explicit_run_id_and_reports_mismatch(tmp_path: Path) -> None:
    ws = tmp_path / "ws-bind"
    res = pkde_dispatch_workorder(_good_spec(), project_dir=str(ws))
    wo_id, run_id = res["work_order_id"], res["run_id"]

    wrong = pkde_manage_cohort(
        action="bind_subagent",
        work_order_id=wo_id,
        subagent_id="conv-1",
        run_id="RUN-999",
        project_dir=str(ws),
    )
    assert wrong["ok"] is False
    assert wrong["unmatched"] and "RUN-999" in wrong["unmatched"][0]["reason"]

    missing = pkde_manage_cohort(
        action="bind_subagent", subagent_bindings='{"WO-404": "conv-x"}', project_dir=str(ws)
    )
    assert missing["ok"] is False and missing["status"] == "NO_MATCHING_WORK_ORDERS"

    malformed = pkde_manage_cohort(
        action="bind_subagent", subagent_bindings="{not json", project_dir=str(ws)
    )
    assert malformed["status"] == "INVALID_BINDINGS"

    cli_bind = pkde_exec(
        f"workorder bind-subagent {wo_id} conv-cli --run-id {run_id} --json",
        project_dir=str(ws),
        auto_refresh_dashboard=False,
    )
    assert cli_bind["ok"] is True, cli_bind
    assert cli_bind["data"]["bound"][0]["run_id"] == run_id
    assert controlstore.read_record(ws, "run", run_id)["conversation_id"] == "conv-cli"


# ---------------------------------------------------------------------------
# MCP + script surfaces match SKILL.md
# ---------------------------------------------------------------------------


def test_mcp_tools_expose_documented_arguments() -> None:
    manage = inspect.signature(mcp_server.pkde_manage_cohort).parameters
    assert {"work_order_id", "subagent_id", "run_id"} <= set(manage)
    boot = inspect.signature(mcp_server.pkde_bootstrap_session).parameters
    assert {"target", "indication", "modality", "fresh"} <= set(boot)


def test_bootstrap_records_target_and_indication(tmp_path: Path) -> None:
    ws = tmp_path / "ws-boot"
    res = pkde_bootstrap_session(
        prompt="Evaluate EGFR for NSCLC",
        project_dir=str(ws),
        target="EGFR",
        indication="NSCLC",
        start_server=False,
    )
    assert res["ok"] is True
    program_yaml = (ws / ".pkde" / "program.yaml").read_text(encoding="utf-8")
    assert "EGFR" in program_yaml and "NSCLC" in program_yaml


def test_dispatch_script_accepts_specs_array_and_rejects_invalid(tmp_path: Path) -> None:
    script = REPO_ROOT / "scripts" / "dispatch_workorder.py"
    ws = tmp_path / "ws-script"
    specs = [
        _good_spec(spec_id="gen"),
        _good_spec(
            spec_id="rev",
            requested_role="scientific-reviewer",
            depends_on=["gen"],
            deliverables={"synthesis_only": True, "layer_1": ["findings/reviews/r.md"]},
        ),
    ]
    ok = subprocess.run(
        [sys.executable, str(script), "--specs", json.dumps(specs), "--project", str(ws)],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    assert ok.returncode == 0, ok.stderr
    out = json.loads(ok.stdout)
    assert out["status"] == "COHORT_DISPATCHED"
    assert out["dispatched_count"] == 1 and out["queued_count"] == 1

    bad = subprocess.run(
        [sys.executable, str(script), "--specs", "[{}]", "--project", str(ws)],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert bad.returncode == 1
    assert json.loads(bad.stdout)["status"] == "INVALID_SPEC"


def test_bundled_script_copies_are_identical() -> None:
    for name in ("dispatch_workorder.py", "start_live_session.py", "pkde_runner.py"):
        copies = [
            REPO_ROOT / "scripts" / name,
            REPO_ROOT / "skills" / "pharmakon-discovery-engine" / "scripts" / name,
            PLUGIN_ROOT / "skills" / "pharmakon-discovery-engine" / "scripts" / name,
        ]
        texts = {p.read_text(encoding="utf-8") for p in copies}
        assert len(texts) == 1, f"{name} copies have diverged"
