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

"""Stdio MCP Server for the Pharmakon Discovery Engine (`pde-engine`).

Exposes the 4 portable tool bridge functions as MCP tools for any MCP-compatible
agent harness:
- ``pde_exec``
- ``pde_dispatch_workorder``
- ``pde_validate_and_gate``
- ``pde_render_dashboard``
"""

from __future__ import annotations

from typing import Any

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore[no-redef]

from .tool_bridge import (
    pde_bootstrap_session as _bootstrap_session,
    pde_dispatch_workorder as _dispatch_workorder,
    pde_exec as _exec,
    pde_log_agent_message as _log_agent_message,
    pde_render_dashboard as _render_dashboard,
    pde_validate_and_gate as _validate_and_gate,
)

mcp = MCPServer(
    "pde-engine",
    instructions=(
        "Pharmakon Discovery Engine (PDE) MCP server providing live session bootstrap "
        "(pde_bootstrap_session), two-phase scientific CLI execution (pde_exec), "
        "multi-agent work-order dispatch (pde_dispatch_workorder), inter-agent "
        "communication logging (pde_log_agent_message), 10-check mechanical "
        "validation gating (pde_validate_and_gate), and the unified interactive "
        "scientific dashboard builder (pde_render_dashboard)."
    ),
)


@mcp.tool()
def pde_bootstrap_session(
    prompt: str,
    program_name: str | None = None,
    stage: int | None = None,
    project_dir: str | None = None,
    host: str = "0.0.0.0",
    port: int = 8765,
    start_server: bool = True,
) -> dict[str, Any]:
    """Initialize a live PDE discovery session from the user's prompt, record the active workspace, build the initial dashboard, and start the non-blocking live server on 0.0.0.0:8765."""
    return _bootstrap_session(
        prompt=prompt,
        program_name=program_name,
        stage=stage,
        project_dir=project_dir,
        host=host,
        port=port,
        start_server=start_server,
    )


@mcp.tool()
def pde_exec(
    command: str,
    project_dir: str | None = None,
    auto_refresh_dashboard: bool = True,
) -> dict[str, Any]:
    """Execute any `pde` CLI command (e.g., 'doctor --json', 'genetics fetch TP53 --json', 'genetics analyze TP53 --json') and return structured JSON output."""
    return _exec(
        command=command,
        project_dir=project_dir,
        auto_refresh_dashboard=auto_refresh_dashboard,
    )


@mcp.tool()
def pde_dispatch_workorder(
    spec: dict[str, Any],
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Automate the 4-step Work Order intake ceremony: create and commit work order, freeze context snapshot, acquire resource lease, create and start run, and return the specialist dispatch brief."""
    return _dispatch_workorder(spec=spec, project_dir=project_dir)


@mcp.tool()
def pde_log_agent_message(
    from_agent: str,
    to_agent: str,
    summary: str,
    work_order_id: str | None = None,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Record an explicit inter-agent communication event in the PDE control plane and refresh the live dashboard."""
    return _log_agent_message(
        from_agent=from_agent,
        to_agent=to_agent,
        summary=summary,
        work_order_id=work_order_id,
        project_dir=project_dir,
    )


@mcp.tool()
def pde_validate_and_gate(
    work_order_id: str,
    run_id: str | None = None,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Run the 10-check mechanical validation gate on a work order (`pde validate check`) and return PASSED, CORRECTION_REQUIRED (up to 2 cycles), or DATA_INTEGRITY_FAILURE."""
    return _validate_and_gate(
        work_order_id=work_order_id,
        run_id=run_id,
        project_dir=project_dir,
    )


@mcp.tool()
def pde_render_dashboard(
    project_dir: str | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Build and render the self-contained PDE Interactive Scientific Dashboard (`dashboard.html`) with the multi-agent lineage graph and all 14 embedded scientific viewers."""
    return _render_dashboard(
        project_dir=project_dir,
        output_path=output_path,
    )


def main() -> None:
    """Run the PDE MCP Server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
