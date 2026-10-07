#!/usr/bin/env python3
"""Atomic Work Order dispatch script for the pharmakon-discovery-engine skill."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pde_plugin.tool_bridge import pde_dispatch_workorder  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dispatch a PDE Work Order and generate the specialist brief."
    )
    parser.add_argument(
        "--spec",
        required=True,
        help="Path to JSON/YAML work order spec file or inline JSON string.",
    )
    parser.add_argument(
        "--project",
        default=None,
        help="Optional PDE project workspace directory override.",
    )
    args = parser.parse_args()

    spec_arg = args.spec.strip()
    if spec_arg.startswith("{"):
        spec = json.loads(spec_arg)
    else:
        spec_path = Path(spec_arg).expanduser().resolve()
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))

    res = pde_dispatch_workorder(spec=spec, project_dir=args.project)
    print(json.dumps(res, indent=2))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
