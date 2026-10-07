#!/usr/bin/env python3
"""Portable CLI runner for PDE commands used inside skills and subagents."""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pde_plugin.tool_bridge import pde_exec  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "Usage: pde_runner.py <pde-subcommand-and-args>",
                },
                indent=2,
            )
        )
        return 2

    cmd_str = " ".join(shlex.quote(arg) for arg in sys.argv[1:])
    result = pde_exec(cmd_str)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else int(result.get("exit_code") or 1)


if __name__ == "__main__":
    raise SystemExit(main())
