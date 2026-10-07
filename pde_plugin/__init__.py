"""Pharmakon Discovery Engine (PDE) Agent Plugin package."""

from .tool_bridge import (
    pde_dispatch_workorder,
    pde_exec,
    pde_render_dashboard,
    pde_validate_and_gate,
)

__all__ = [
    "pde_exec",
    "pde_dispatch_workorder",
    "pde_validate_and_gate",
    "pde_render_dashboard",
]
