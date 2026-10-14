#!/usr/bin/env python3
"""Portable CLI runner for PkDE commands used inside skills and subagents."""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

def _resolve_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pkde_plugin").is_dir() and (parent / "tools" / "pkde").is_dir():
            return parent
    return here.parents[1]


REPO_ROOT = _resolve_repo_root()
for _p in (str(REPO_ROOT / "tools"), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pkde_plugin.tool_bridge import pkde_exec  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "Usage: pkde_runner.py <pkde-subcommand-and-args>",
                },
                indent=2,
            )
        )
        return 2

    cmd_str = " ".join(shlex.quote(arg) for arg in sys.argv[1:])
    result = pkde_exec(cmd_str)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else int(result.get("exit_code") or 1)


if __name__ == "__main__":
    raise SystemExit(main())
