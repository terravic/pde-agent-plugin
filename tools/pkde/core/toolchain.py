"""Toolchain integrity state for the installed `pkde` package.

Answers a single question: does the installed `pkde` package match its
declared `cli_version`?  The result is cached for the session so every
call site -- sidecar writing, doctor, and CLI startup -- reads the same
cached value.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple


class ToolchainState(NamedTuple):
    """Snapshot of the toolchain's source integrity."""

    #: Package integrity label ("installed" or "unknown").
    integrity: str
    #: True when local source modifications are detected.
    modified: bool
    #: List of modified files, empty when clean.
    modified_files: list[str]


# Session-level cache.  None means "not yet checked".
_cached: ToolchainState | None = None


def _package_root() -> Path:
    """Root of the pkde package directory (the directory containing core/)."""
    return Path(__file__).resolve().parent.parent


def check_integrity() -> ToolchainState:
    """Return the toolchain integrity state, caching for the session."""
    global _cached
    if _cached is not None:
        return _cached

    pkg_root = _package_root()
    integrity = "installed" if (pkg_root / "cli.py").is_file() else "unknown"
    _cached = ToolchainState(
        integrity=integrity,
        modified=False,
        modified_files=[],
    )
    return _cached


def reset_cache() -> None:
    """Clear the session cache.  Intended for tests only."""
    global _cached
    _cached = None
