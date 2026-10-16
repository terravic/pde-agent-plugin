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

"""Stdio MCP Server for the Pharmakon Discovery Engine (`pkde-engine`).

Exposes the 6 portable tool bridge functions as MCP tools for any MCP-compatible
agent harness:
- ``pkde_bootstrap_session``
- ``pkde_exec``
- ``pkde_dispatch_workorder``
- ``pkde_log_agent_message``
- ``pkde_validate_and_gate``
- ``pkde_render_dashboard``
"""

from __future__ import annotations

import inspect
import json
import sys
from typing import Any, Callable

try:
    from mcp.types import ToolAnnotations
    try:
        from mcp.server.mcpserver import MCPServer
    except ImportError:
        from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore[no-redef]
except ImportError:  # pragma: no cover

    class ToolAnnotations:  # type: ignore[no-redef]
        def __init__(self, **kwargs: Any) -> None:
            self.__dict__.update(kwargs)

    class MCPServer:  # type: ignore[no-redef]
        """Zero-dependency stdlib JSON-RPC 2.0 stdio MCP server fallback."""

        def __init__(self, name: str, instructions: str = "") -> None:
            self.name = name
            self.instructions = instructions
            self._tools: dict[str, tuple[Callable[..., Any], dict[str, Any]]] = {}

        def tool(self, annotations: Any = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
                sig = inspect.signature(fn)
                props: dict[str, Any] = {}
                required: list[str] = []
                for p_name, param in sig.parameters.items():
                    ann = str(param.annotation)
                    if "int" in ann:
                        p_type = "integer"
                    elif "bool" in ann:
                        p_type = "boolean"
                    elif "dict" in ann:
                        p_type = "object"
                    else:
                        p_type = "string"
                    props[p_name] = {"type": p_type}
                    if param.default is inspect.Parameter.empty:
                        required.append(p_name)
                schema = {
                    "name": fn.__name__,
                    "description": (inspect.getdoc(fn) or "").strip(),
                    "inputSchema": {
                        "type": "object",
                        "properties": props,
                        "required": required,
                    },
                }
                self._tools[fn.__name__] = (fn, schema)
                return fn

            return _decorator

        def handle_jsonrpc_message(self, msg: dict[str, Any]) -> dict[str, Any] | None:
            method = msg.get("method", "")
            msg_id = msg.get("id")
            params = msg.get("params") or {}
            if msg_id is None or method.startswith("notifications/"):
                return None
            if method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": self.name, "version": "0.3.0"},
                        "instructions": self.instructions,
                    },
                }
            if method == "ping":
                return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
            if method == "tools/list":
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"tools": [schema for _, schema in self._tools.values()]},
                }
            if method == "tools/call":
                t_name = params.get("name", "")
                t_args = params.get("arguments") or {}
                if t_name not in self._tools:
                    return {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32601, "message": f"Unknown tool: {t_name}"},
                    }
                fn, _ = self._tools[t_name]
                try:
                    res = fn(**t_args)
                    return {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [{"type": "text", "text": json.dumps(res)}],
                            "isError": False,
                        },
                    }
                except Exception as exc:
                    return {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [{"type": "text", "text": json.dumps({"ok": False, "error": str(exc)})}],
                            "isError": True,
                        },
                    }
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        def run(self) -> None:
            for raw_line in sys.stdin:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                resp = self.handle_jsonrpc_message(msg)
                if resp is not None:
                    sys.stdout.write(json.dumps(resp) + "\n")
                    sys.stdout.flush()


from .tool_bridge import (
    pkde_bootstrap_session as _bootstrap_session,
    pkde_dispatch_workorder as _dispatch_workorder,
    pkde_exec as _exec,
    pkde_log_agent_message as _log_agent_message,
    pkde_render_dashboard as _render_dashboard,
    pkde_validate_and_gate as _validate_and_gate,
)

mcp = MCPServer(
    "pkde-engine",
    instructions=(
        "Pharmakon Discovery Engine (PkDE) MCP server providing live session bootstrap "
        "(pkde_bootstrap_session), two-phase scientific CLI execution (pkde_exec), "
        "multi-agent work-order dispatch (pkde_dispatch_workorder), inter-agent "
        "communication logging (pkde_log_agent_message), 10-check mechanical "
        "validation gating (pkde_validate_and_gate), and the unified interactive "
        "scientific dashboard builder (pkde_render_dashboard)."
    ),
)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    )
)
def pkde_bootstrap_session(
    prompt: str,
    program_name: str | None = None,
    stage: int | None = None,
    project_dir: str | None = None,
    host: str = "0.0.0.0",
    port: int = 8765,
    start_server: bool = True,
) -> dict[str, Any]:
    """Initialize a live PkDE discovery session from the user's prompt, record the active workspace, build the initial dashboard, and start the non-blocking live server on 0.0.0.0:8765."""
    return _bootstrap_session(
        prompt=prompt,
        program_name=program_name,
        stage=stage,
        project_dir=project_dir,
        host=host,
        port=port,
        start_server=start_server,
    )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=True,
    )
)
def pkde_exec(
    command: str,
    project_dir: str | None = None,
    auto_refresh_dashboard: bool = True,
) -> dict[str, Any]:
    """Execute any `pkde` CLI command (e.g., 'doctor --json', 'genetics fetch TP53 --json', 'genetics analyze TP53 --json') and return structured JSON output."""
    return _exec(
        command=command,
        project_dir=project_dir,
        auto_refresh_dashboard=auto_refresh_dashboard,
    )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    )
)
def pkde_dispatch_workorder(
    spec: dict[str, Any],
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Automate the 4-step Work Order intake ceremony: create and commit work order, freeze context snapshot, acquire resource lease, create and start run, and return the specialist dispatch brief."""
    return _dispatch_workorder(spec=spec, project_dir=project_dir)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    )
)
def pkde_log_agent_message(
    from_agent: str,
    to_agent: str,
    summary: str,
    work_order_id: str | None = None,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Record an explicit inter-agent communication event in the PkDE control plane and refresh the live dashboard."""
    return _log_agent_message(
        from_agent=from_agent,
        to_agent=to_agent,
        summary=summary,
        work_order_id=work_order_id,
        project_dir=project_dir,
    )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    )
)
def pkde_validate_and_gate(
    work_order_id: str,
    run_id: str | None = None,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Run the 10-check mechanical validation gate on a work order (`pkde validate check`) and return PASSED, CORRECTION_REQUIRED (up to 2 cycles), or DATA_INTEGRITY_FAILURE."""
    return _validate_and_gate(
        work_order_id=work_order_id,
        run_id=run_id,
        project_dir=project_dir,
    )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
def pkde_render_dashboard(
    project_dir: str | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Build and render the self-contained PkDE Interactive Scientific Dashboard (`dashboard.html`) with the multi-agent lineage graph and all 14 embedded scientific viewers."""
    return _render_dashboard(
        project_dir=project_dir,
        output_path=output_path,
    )


def main() -> None:
    """Run the PkDE MCP Server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
