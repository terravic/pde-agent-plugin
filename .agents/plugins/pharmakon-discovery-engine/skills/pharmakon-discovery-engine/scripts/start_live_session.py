#!/usr/bin/env python3
"""Initialize a live PDE discovery session from the user's prompt and start the dashboard server."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pde_plugin.tool_bridge import pde_bootstrap_session  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap a PDE session from the user prompt and start the live dashboard server on 0.0.0.0:8765."
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="User prompt or scientific question initiating the discovery session.",
    )
    parser.add_argument(
        "--program-name",
        default=None,
        help="Optional program display name.",
    )
    parser.add_argument(
        "--stage",
        type=int,
        default=None,
        help="Optional initial stage number (0-4).",
    )
    parser.add_argument(
        "--project",
        default=None,
        help="Optional PDE project workspace directory override.",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host interface to bind (default: 0.0.0.0).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to bind (default: 8765).",
    )
    parser.add_argument(
        "--no-serve",
        action="store_true",
        help="Build the initial dashboard without starting the background HTTP/SSE server.",
    )
    args = parser.parse_args()

    res = pde_bootstrap_session(
        prompt=args.prompt,
        program_name=args.program_name,
        stage=args.stage,
        project_dir=args.project,
        host=args.host,
        port=args.port,
        start_server=not args.no_serve,
    )
    print(json.dumps(res, indent=2))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
