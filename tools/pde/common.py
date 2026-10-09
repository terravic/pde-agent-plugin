"""Shared click plumbing: state, error rendering, common options."""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click

from .core import controlstore, thresholds as thresholds_mod
from .core.context import ProjectContext, resolve_project
from .core.errors import ArtifactError, PDEError
from .core.output import Emitter

_TOOL_ROLE_MAP: dict[str, str] = {
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
    "coscientist": "hypex-supervisor",
    "hypex": "hypex-supervisor",
    "hypothesis": "science-program-lead",
}


@dataclass
class AppState:
    """Per-invocation state carried on the click context."""

    project_override: str | None = None
    _project: ProjectContext | None = None

    def project(self) -> ProjectContext:
        """Resolve the project root once per invocation."""
        if self._project is None:
            self._project = resolve_project(self.project_override)
        return self._project


pass_state = click.make_pass_decorator(AppState, ensure=True)


class PDEGroup(click.Group):
    """Group that renders PDEError cleanly and uses its exit code.

    Failures print a reason and exit non-zero. Nothing is synthesized on
    any failure path.
    """

    def invoke(self, ctx: click.Context) -> Any:
        try:
            return super().invoke(ctx)
        except PDEError as exc:
            click.echo(exc.render(), err=True)
            sys.exit(exc.exit_code)


#: The phase-2 subcommand name. The two-phase contract names this
#: command specifically (tool-design-guidance §3), so keying the guard on
#: the name is not a heuristic — it is the contract, and a phase-2
#: command called something else is already outside it.
ANALYZE = "analyze"


def is_phase_two(name: str) -> bool:
    """Is this subcommand name a phase-2 command?

    `analyze`, and also `analyze-<something>` — a tool with two kinds of
    phase-1 output needs two analysers, and `analyze-prediction` and
    `analyze-ism` are both squarely phase 2. Matching only the exact name
    left them unguarded, which is the same defect the guard was written
    to remove: a rule that holds for the commands someone remembered.
    """
    return (
        name == ANALYZE
        or name.startswith(f"{ANALYZE}-")
        or name == "assess"
        or name.startswith("assess-")
    )


#: Injected into every phase-2 command by the root walk, rather than
#: written on each one. An `--overwrite` a command author has to remember
#: to add is missing from exactly the command whose author did not think
#: about the second opinion.
OVERWRITE_OPTION = click.Option(
    ["--overwrite"],
    is_flag=True,
    help="Replace an existing analysis that disagrees with this one. "
    "Without it, a conflicting write is refused (exit 9).",
)

OVERWRITE_CROSS_WO_OPTION = click.Option(
    ["--overwrite-cross-wo"],
    is_flag=True,
    help="Allow overwriting an analysis attributed to a different work order. "
    "Without it, cross-work-order overwrite is refused even with --overwrite.",
)


EXEMPT_PHASE_TWO_GROUPS: frozenset[str] = frozenset(
    {
        "site",
        "dashboard",
        "workorder",
        "wo",
        "run",
        "validate",
        "doctor",
        "env",
        "init",
        "relays",
        "schema",
        "tools",
        "program",
        "triage",
        "dossier",
    }
)


def enforce_phase_two(group: click.Group) -> None:
    """Apply the phase-2 contract and passive telemetry to domain commands.

    Two structural properties applied to phase-2 (`analyze`/`assess`) commands:

    * **Offline.** The shared HTTP client is latched for the rest of the
      invocation, so a lookup added to a phase-2 command raises instead of
      quietly making re-analysis depend on an endpoint.
    * **Non-destructive.** `--overwrite` is injected, and without it a
      write that would replace a *differing* analysis is refused.

    In addition, all non-exempt domain commands (both Phase 1 and Phase 2)
    automatically emit lightweight passive telemetry events
    (`tool.started` / `tool.completed` / `tool.failed`) into
    `.pde/control/events.ndjson` when executed inside a PDE workspace.
    """
    from .core import http, provenance

    for name, command in group.commands.items():
        if name in EXEMPT_PHASE_TWO_GROUPS:
            continue
        if isinstance(command, click.Group):
            enforce_phase_two(command)
            continue
        is_p2 = is_phase_two(name)
        original = command.callback
        if original is None or getattr(original, "_phase_two_guarded", False):
            continue

        if is_p2:
            if not any(p.name == "overwrite" for p in command.params):
                command.params.append(OVERWRITE_OPTION)
            if not any(p.name == "overwrite_cross_wo" for p in command.params):
                command.params.append(OVERWRITE_CROSS_WO_OPTION)

        def guarded(
            *args: Any,
            _original=original,
            _group=group.name or "pde",
            _name=name,
            _is_p2=is_p2,
            **kwargs: Any,
        ):
            if _is_p2:
                # Injected by this wrapper, so consumed by it: the wrapped
                # callback never declared the parameter.
                provenance.allow_overwrite(bool(kwargs.pop("overwrite", False)))
                provenance.allow_overwrite_cross_wo(
                    bool(kwargs.pop("overwrite_cross_wo", False))
                )
                http.forbid_network(
                    f"`{_group} {_name}` is phase 2: it reads what phase 1 wrote "
                    "and never queries an endpoint"
                )

            project_root: Path | None = None
            phase = "phase2" if _is_p2 else "phase1"
            actor = os.environ.get("PDE_AGENT_ROLE") or _TOOL_ROLE_MAP.get(
                _group, "computational-biologist"
            )
            t0 = time.monotonic()
            try:
                ctx = click.get_current_context(silent=True)
                state = ctx.find_object(AppState) if ctx is not None else None
                if state is not None:
                    cand_root = state.project().root
                    if (cand_root / ".pde").is_dir():
                        project_root = cand_root
                        arg_preview: list[str] = []
                        for k, v in kwargs.items():
                            if (
                                k in ("as_json", "quiet", "out", "from_dir", "state")
                                or v is None
                                or isinstance(v, (bool, AppState))
                            ):
                                continue
                            arg_preview.append(str(v)[:60])
                        controlstore.append_event(
                            project_root,
                            {
                                "type": "tool.started",
                                "subject_id": f"{_group}.{_name}",
                                "from_state": "idle",
                                "to_state": "running",
                                "actor": actor,
                                "detail": {
                                    "tool": _group,
                                    "subcommand": _name,
                                    "phase": phase,
                                    "args": arg_preview[:3],
                                },
                            },
                        )
            except Exception:
                project_root = None

            try:
                res = _original(*args, **kwargs)
                if project_root is not None:
                    try:
                        controlstore.append_event(
                            project_root,
                            {
                                "type": "tool.completed",
                                "subject_id": f"{_group}.{_name}",
                                "from_state": "running",
                                "to_state": "succeeded",
                                "actor": actor,
                                "detail": {
                                    "tool": _group,
                                    "subcommand": _name,
                                    "phase": phase,
                                    "duration_ms": int((time.monotonic() - t0) * 1000),
                                },
                            },
                        )
                    except Exception:
                        pass
                return res
            except Exception as exc:
                if project_root is not None:
                    try:
                        controlstore.append_event(
                            project_root,
                            {
                                "type": "tool.failed",
                                "subject_id": f"{_group}.{_name}",
                                "from_state": "running",
                                "to_state": "failed",
                                "actor": actor,
                                "detail": {
                                    "tool": _group,
                                    "subcommand": _name,
                                    "phase": phase,
                                    "exit_code": int(getattr(exc, "exit_code", 1)),
                                    "duration_ms": int((time.monotonic() - t0) * 1000),
                                },
                            },
                        )
                    except Exception:
                        pass
                raise

        guarded._phase_two_guarded = True  # type: ignore[attr-defined]
        command.callback = guarded


def output_options(func: Callable) -> Callable:
    """--json and --quiet, present on every subcommand (§6)."""
    func = click.option(
        "--json", "as_json", is_flag=True, help="Emit a machine-readable JSON record."
    )(func)
    func = click.option("--quiet", is_flag=True, help="Emit output paths only.")(func)
    return func


def out_option(func: Callable) -> Callable:
    """--out override for the artifact-class default directory (§4)."""
    return click.option(
        "--out",
        default=None,
        help="Override the default output directory (relative paths resolve "
        "against the project root, never CWD).",
    )(func)


def name_option(func: Callable) -> Callable:
    """--name: human-readable compound name alias for filenames and metadata.

    When provided, a slugified version of the name is used instead of the
    SMILES-derived slug for output filenames.  The original name is also
    recorded in the provenance sidecar under ``compound_name``.  When
    omitted, behavior is identical to the default (SMILES-derived slug).
    """
    return click.option(
        "--name",
        default=None,
        help="Human-readable compound name alias for filenames and metadata.",
    )(func)


def from_option(func: Callable) -> Callable:
    """--from: where phase 2 READS its inputs, decoupled from --out.

    `analyze` used one directory for both, which made an independent
    re-run impossible: re-running to check a verdict overwrote the very
    artifact being checked, and the reviewer then compared their output
    with itself. `--out` alone could not help, because redirecting the
    output also redirected the lookup and the input was no longer found.

    So a reviewer regenerates a verdict without touching the evidence:

        pde genetics analyze TP53 --out review/2026-08-18

    Defaults to the artifact-class directory, which is where phase 1
    writes. Nothing is searched for and nothing falls back — an input
    directory that does not hold the artifact is an error, not a cue to
    look somewhere else.
    """
    return click.option(
        "--from",
        "from_dir",
        default=None,
        help="Read phase-1 artifacts from here instead of the default "
        "directory (relative paths resolve against the project root).",
    )(func)


def beside_or_out(
    state: AppState, source: Path, filename: str, out: str | None
) -> Path:
    """Destination for an `analyze` that took its input as a path.

    Where the input is named explicitly there is nothing for `--from` to
    do, but the destructive half of the problem is still there: writing
    the verdict beside the artifact it read means a second opinion
    overwrites the first one, and the reviewer then compares their own
    output with itself.

    So the default stays beside the source — that is where phase 1 put
    it and where every existing skill looks — and `--out` moves only the
    verdict, never the lookup. The input is a path either way, so the
    two cannot be confused as they were on the identifier-based
    commands.
    """
    if out is None:
        return source.parent / filename
    override = Path(out)
    target = override if override.is_absolute() else state.project().root / override
    target.mkdir(parents=True, exist_ok=True)
    return target / filename


def emitter(as_json: bool, quiet: bool) -> Emitter:
    return Emitter(as_json=as_json, quiet=quiet)


def resolve_artifact(state: AppState, path: str, what: str = "artifact") -> Path:
    """Resolve an input artifact path against the project root, not CWD.

    Agents are unreliable about working directory (§4), so a relative
    path means "relative to the program directory". A bare path that
    exists in CWD but not under the project root is still an error —
    silently reading the wrong file is worse than failing.
    """
    candidate = Path(path)
    resolved = (
        candidate if candidate.is_absolute() else state.project().root / candidate
    )
    if not resolved.is_file():
        raise ArtifactError(
            f"{what} not found: {resolved}",
            detail=f"relative paths resolve against the project root "
            f"({state.project().root}), never the current directory",
            remedy="run the corresponding phase-1 subcommand first, or pass a project-relative path",
        )
    return resolved


def load_thresholds(
    state: AppState, name: str, overrides: dict[str, Any] | None = None
) -> thresholds_mod.ThresholdSet:
    return thresholds_mod.load(name, state.project().root, overrides)
