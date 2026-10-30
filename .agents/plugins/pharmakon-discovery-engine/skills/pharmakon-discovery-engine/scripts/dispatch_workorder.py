#!/usr/bin/env python3
"""Atomic Work Order dispatch script for the pharmakon-discovery-engine skill.

Accepts a single work-order spec or a multi-persona cohort, either inline
(JSON object / JSON array / ``{"work_orders": [...]}``) or as a path to a
JSON/YAML file. Cohorts are routed to ``pkde_dispatch_cohort`` (wave
scheduling); single specs to ``pkde_dispatch_workorder``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


def _resolve_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pkde_plugin").is_dir() and (parent / "tools" / "pkde").is_dir():
            return parent
    raise SystemExit(
        f"dispatch_workorder.py: cannot locate the PkDE repository root above {here} "
        "(expected sibling 'pkde_plugin/' and 'tools/pkde/' directories)"
    )


REPO_ROOT = _resolve_repo_root()
for _p in (str(REPO_ROOT / "tools"), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pkde_plugin.tool_bridge import (  # noqa: E402
    pkde_dispatch_cohort,
    pkde_dispatch_workorder,
)


def _load_spec_arg(raw: str) -> Any:
    text = raw.strip()
    if text.startswith("{") or text.startswith("["):
        try:
            return json.loads(text)
        except ValueError as exc:
            raise SystemExit(f"dispatch_workorder.py: invalid inline JSON: {exc}") from exc
    spec_path = Path(text).expanduser().resolve()
    if not spec_path.is_file():
        raise SystemExit(f"dispatch_workorder.py: spec file not found: {spec_path}")
    raw_text = spec_path.read_text(encoding="utf-8")
    if spec_path.suffix.lower() in (".yaml", ".yml"):
        if yaml is None:
            raise SystemExit("dispatch_workorder.py: PyYAML is required to read YAML specs")
        return yaml.safe_load(raw_text)
    return json.loads(raw_text)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Dispatch a PkDE Work Order (single spec) or a multi-persona cohort "
            "and emit specialist briefs plus ready-to-call subagent_invocations."
        )
    )
    parser.add_argument(
        "--specs",
        "--spec",
        "--from",
        dest="specs",
        required=True,
        help=(
            "Inline JSON (object, array, or {\"work_orders\": [...]}) or a path to a "
            "JSON/YAML file containing the same."
        ),
    )
    parser.add_argument(
        "--project",
        default=None,
        help="Optional PkDE project workspace directory override.",
    )
    args = parser.parse_args()

    loaded = _load_spec_arg(args.specs)
    if isinstance(loaded, dict) and isinstance(loaded.get("work_orders"), list):
        res = pkde_dispatch_cohort(specs=loaded["work_orders"], project_dir=args.project)
    elif isinstance(loaded, list):
        res = pkde_dispatch_cohort(specs=loaded, project_dir=args.project)
    elif isinstance(loaded, dict):
        res = pkde_dispatch_workorder(spec=loaded, project_dir=args.project)
    else:
        raise SystemExit(
            "dispatch_workorder.py: spec must be a JSON/YAML mapping, a list of mappings, "
            "or {\"work_orders\": [...]}"
        )
    print(json.dumps(res, indent=2))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
