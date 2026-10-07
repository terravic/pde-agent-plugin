#!/usr/bin/env python3
"""Render the self-contained PDE Interactive Scientific Dashboard HTML."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pde_plugin.tool_bridge import pde_render_dashboard  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the self-contained PDE Interactive Scientific Dashboard HTML."
    )
    parser.add_argument(
        "--project",
        default=None,
        help="Optional PDE project workspace directory override.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Optional output path for dashboard.html.",
    )
    args = parser.parse_args()

    res = pde_render_dashboard(
        project_dir=args.project,
        output_path=args.output,
    )
    print(json.dumps(res, indent=2))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
