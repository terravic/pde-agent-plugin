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

"""Security, offline asset isolation, input validation, and WCAG 2.2 AA tests."""

from __future__ import annotations

import http.client
import json
import os
import re
import sys
import threading
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pkde.commands import alphafold as af_mod
from pkde.commands import alphagenome as ag_mod
from pkde.commands import dashboard as dash_mod
from pkde.core.errors import UsageError


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    assert len(h) == 6, f"Expected 6-digit hex color, got {hex_color!r}"
    return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def _relative_luminance(hex_color: str) -> float:
    def _lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (_lin(v) for v in _hex_to_rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(fg: str, bg: str) -> float:
    l1 = _relative_luminance(fg)
    l2 = _relative_luminance(bg)
    hi, lo = (l1, l2) if l1 >= l2 else (l2, l1)
    return (hi + 0.05) / (lo + 0.05)


# ---------------------------------------------------------------------------
# 1. Offline Asset Isolation & CSP
# ---------------------------------------------------------------------------


def test_zero_external_cdn_tags_in_html_templates_and_dashboards() -> None:
    """No HTML template, viewer, or built dashboard may load external CDN assets."""
    forbidden_hosts = ("cdn.jsdelivr.net", "fonts.googleapis.com", "fonts.gstatic.com")
    html_paths = list((REPO_ROOT / "tools" / "pkde" / "site_templates").rglob("*.html"))
    for candidate in (
        REPO_ROOT / "dashboard.html",
        REPO_ROOT / ".pkde-workspace" / "dashboard.html",
        REPO_ROOT / ".pkde-workspace" / "default-program" / "dashboard.html",
        REPO_ROOT / ".pkde-workspace" / "live-multi-agent-verify" / "dashboard.html",
    ):
        if candidate.is_file():
            html_paths.append(candidate)

    assert len(html_paths) >= 18
    for path in html_paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for host in forbidden_hosts:
            assert host not in text, f"Forbidden external CDN reference {host!r} in {path}"


def test_all_14_static_viewers_enforce_csp_and_relative_file_validation() -> None:
    """Every static viewer must declare a strict CSP meta tag and reject external ?file= URLs."""
    viewers_dir = REPO_ROOT / "tools" / "pkde" / "site_templates" / "viewers"
    viewer_files = sorted(viewers_dir.glob("*.html"))
    assert len(viewer_files) == 14
    for vf in viewer_files:
        text = vf.read_text(encoding="utf-8")
        assert 'http-equiv="Content-Security-Policy"' in text, f"Missing CSP meta tag in {vf.name}"
        assert "isSafeRelativeFile" in text, f"Missing relative path guard in {vf.name}"
        assert ":focus-visible" in text, f"Missing :focus-visible outline rule in {vf.name}"
        assert not re.search(r"<script[^>]+src=[\"']https?://", text, re.IGNORECASE), (
            f"External script src found in {vf.name}"
        )


def test_dashboard_template_has_csp_no_inline_dynamic_onclick_and_delegation() -> None:
    """Dashboard HTML must enforce CSP, use delegated handlers, and omit dynamic onclick interpolation."""
    dash_tpl = (REPO_ROOT / "tools" / "pkde" / "site_templates" / "dashboard.html").read_text(
        encoding="utf-8"
    )
    assert 'http-equiv="Content-Security-Policy"' in dash_tpl
    assert "data-pkde-action" in dash_tpl
    assert "data-pkde-arg" in dash_tpl
    assert "closest('[data-pkde-action]')" in dash_tpl
    assert "<h2 " in dash_tpl
    assert "<nav " in dash_tpl
    assert ":focus-visible" in dash_tpl
    assert ".sr-only" in dash_tpl
    # Dynamic interpolated onclick="${...}" or onclick="...('${escapeHtml(...)')" must not exist
    assert not re.search(r'onclick="[^"]*\$\{', dash_tpl), (
        "Dynamic JS string interpolation inside inline onclick attribute detected"
    )


# ---------------------------------------------------------------------------
# 2. Markdown XSS Sanitization & Path Confinement
# ---------------------------------------------------------------------------


def test_markdown_sanitizer_strips_xss_links_and_external_images(tmp_path: Path) -> None:
    """Rendered Markdown must escape raw HTML, neutralize javascript:/data: links, and block external images."""
    malicious_md = (
        "# Probe\n\n"
        "<script>alert(1)</script>\n\n"
        "[Click me](javascript:alert(1))\n\n"
        "[Data link](data:text/html,<script>alert(2)</script>)\n\n"
        "![Tracker](https://tracker.example.invalid/pixel.png)\n\n"
        "[Safe link](https://example.org/docs)\n"
    )
    rendered, _, _ = dash_mod._render_markdown_with_annotations(malicious_md, tmp_path, "findings/probe.md")
    assert "<script>" not in rendered.lower()
    assert "javascript:" not in rendered.lower()
    assert "data:text/html" not in rendered.lower()
    assert "<img" not in rendered.lower()
    assert "[EXTERNAL IMAGE BLOCKED]" in rendered
    assert 'href="https://example.org/docs"' in rendered


def test_resolve_live_project_root_confines_to_repo_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """active-project.json pointing outside the repository root must be rejected."""
    fake_repo = tmp_path / "repo"
    fake_ws = fake_repo / ".pkde-workspace"
    fake_ws.mkdir(parents=True)
    outside = tmp_path / "outside-dir"
    outside.mkdir(parents=True)

    ptr = fake_ws / "active-project.json"
    ptr.write_text(json.dumps({"project_root": str(outside)}), encoding="utf-8")

    monkeypatch.setattr(dash_mod, "_repo_root", lambda: fake_repo)
    monkeypatch.setattr(dash_mod, "_active_project_pointer_path", lambda: ptr)

    resolved = dash_mod.resolve_live_project_root(fake_ws)
    assert resolved == fake_ws.resolve()


# ---------------------------------------------------------------------------
# 3. Live Dashboard HTTP Server Security Controls
# ---------------------------------------------------------------------------


def test_dashboard_default_host_is_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default bind host must be loopback 127.0.0.1 unless explicitly overridden."""
    monkeypatch.delenv("PKDE_DASHBOARD_HOST", raising=False)
    assert dash_mod._default_dashboard_host() == "127.0.0.1"
    monkeypatch.setenv("PKDE_DASHBOARD_HOST", "0.0.0.0")
    assert dash_mod._default_dashboard_host() == "0.0.0.0"


def test_dashboard_http_server_headers_same_origin_and_static_404(tmp_path: Path) -> None:
    """Live HTTP server must set security headers, reject cross-origin API reads, and return static 404."""
    proj = tmp_path / "proj"
    (proj / ".pkde" / "control").mkdir(parents=True)
    (proj / ".pkde" / "program.yaml").write_text("name: SecurityTest\nstage: 1\n", encoding="utf-8")

    handler_cls = dash_mod.create_dashboard_http_handler(proj)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # 1. GET / -> 200 with full security headers
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8", errors="replace")
        assert resp.status == 200
        csp = resp.getheader("Content-Security-Policy") or ""
        assert "default-src 'self'" in csp
        assert "object-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp
        assert resp.getheader("X-Content-Type-Options") == "nosniff"
        assert resp.getheader("X-Frame-Options") == "DENY"
        assert resp.getheader("Referrer-Policy") == "no-referrer"
        assert resp.getheader("Cross-Origin-Resource-Policy") == "same-origin"
        assert "cdn.jsdelivr.net" not in body
        conn.close()

        # 2. Cross-origin GET /api/bundle -> 403 Forbidden
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/bundle", headers={"Origin": "https://evil.example"})
        resp = conn.getresponse()
        _ = resp.read()
        assert resp.status == 403
        conn.close()

        # 3. Cross-origin GET /api/stream -> 403 Forbidden
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/stream?once=1", headers={"Origin": "https://evil.example"})
        resp = conn.getresponse()
        _ = resp.read()
        assert resp.status == 403
        conn.close()

        # 4. Same-origin GET /api/bundle -> 200 JSON without Access-Control-Allow-Origin: *
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/bundle", headers={"Origin": f"http://127.0.0.1:{port}"})
        resp = conn.getresponse()
        payload = json.loads(resp.read().decode("utf-8"))
        assert resp.status == 200
        assert resp.getheader("Access-Control-Allow-Origin") is None
        assert "program" in payload
        conn.close()

        # 5. Unknown endpoint -> static 404 JSON that does not echo user input
        probe_path = "/nonexistent-probe-<svg-onload=alert(1)>"
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", probe_path)
        resp = conn.getresponse()
        err_body = resp.read().decode("utf-8")
        assert resp.status == 404
        assert json.loads(err_body) == {"error": "Unknown endpoint"}
        assert "probe" not in err_body
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_pid_identity_guard_rejects_current_pytest_process() -> None:
    """PID guard must refuse to identify non-dashboard processes (such as pytest) as a dashboard server."""
    assert dash_mod._is_pkde_dashboard_pid(os.getpid()) is False
    assert dash_mod._is_pkde_dashboard_pid(-1) is False


# ---------------------------------------------------------------------------
# 4. Cloud Infrastructure De-identification & Configuration Enforcement
# ---------------------------------------------------------------------------


def test_cloud_endpoints_require_explicit_env_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """AlphaFold 3 and AlphaGenome dedicated endpoints must not fall back to hardcoded defaults."""
    monkeypatch.setattr(ag_mod, "AG_PROJECT", "")
    monkeypatch.setattr(ag_mod, "AG_ENDPOINT_ID", "")
    monkeypatch.setattr(ag_mod, "AG_ENDPOINT_DNS", "")
    with pytest.raises(UsageError):
        ag_mod._rawpredict_url()

    assert af_mod.AF3_PROJECT == os.environ.get("PKDE_AF3_PROJECT", "").strip()


# ---------------------------------------------------------------------------
# 5. MCP Server Strict Schema Validation (JSON-RPC -32602)
# ---------------------------------------------------------------------------


def test_mcp_fallback_jsonrpc_validates_tool_arguments() -> None:
    """Stdlib MCP JSON-RPC fallback must reject unknown keys, missing required params, and wrong types."""
    # Force-load the stdlib fallback class directly by compiling the fallback branch in isolation
    # or invoking it directly if present on pkde_plugin.mcp_server.
    from pkde_plugin import mcp_server as mcp_mod

    if hasattr(mcp_mod.mcp, "handle_jsonrpc_message"):
        srv = mcp_mod.mcp
    else:
        # Instantiate the stdlib MCPServer class directly by temporarily shadowing mcp.server
        import importlib
        import types

        fake_mcp = types.ModuleType("mcp")
        old_mcp = sys.modules.get("mcp")
        old_mcp_server = sys.modules.get("mcp.server")
        old_mcp_types = sys.modules.get("mcp.types")
        sys.modules["mcp"] = fake_mcp
        sys.modules["mcp.server"] = None  # type: ignore[assignment]
        sys.modules["mcp.types"] = None  # type: ignore[assignment]
        try:
            reloaded = importlib.reload(mcp_mod)
            srv = reloaded.mcp
        finally:
            if old_mcp is not None:
                sys.modules["mcp"] = old_mcp
            else:
                sys.modules.pop("mcp", None)
            if old_mcp_server is not None:
                sys.modules["mcp.server"] = old_mcp_server
            else:
                sys.modules.pop("mcp.server", None)
            if old_mcp_types is not None:
                sys.modules["mcp.types"] = old_mcp_types
            else:
                sys.modules.pop("mcp.types", None)
            importlib.reload(mcp_mod)

    # 1. Unknown argument key -> -32602
    r1 = srv.handle_jsonrpc_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "pkde_render_dashboard", "arguments": {"unexpected_param": 123}},
        }
    )
    assert r1 is not None and r1["error"]["code"] == -32602

    # 2. Missing required argument -> -32602
    r2 = srv.handle_jsonrpc_message(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "pkde_exec", "arguments": {}},
        }
    )
    assert r2 is not None and r2["error"]["code"] == -32602

    # 3. Wrong argument type (integer instead of string) -> -32602
    r3 = srv.handle_jsonrpc_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "pkde_exec", "arguments": {"command": 42}},
        }
    )
    assert r3 is not None and r3["error"]["code"] == -32602

    # 4. Non-dict arguments -> -32602
    r4 = srv.handle_jsonrpc_message(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "pkde_render_dashboard", "arguments": ["bad"]},
        }
    )
    assert r4 is not None and r4["error"]["code"] == -32602


# ---------------------------------------------------------------------------
# 6. WCAG 2.2 AA Contrast Verification & Legal Templates
# ---------------------------------------------------------------------------


def test_wcag_aa_contrast_ratios_for_light_and_dark_themes() -> None:
    """All primary, secondary, link, and warning text tokens must meet WCAG 2.2 AA (>= 4.5:1)."""
    dash_tpl = (REPO_ROOT / "tools" / "pkde" / "site_templates" / "dashboard.html").read_text(
        encoding="utf-8"
    )
    base_tpl = (REPO_ROOT / "tools" / "pkde" / "site_templates" / "base.html").read_text(
        encoding="utf-8"
    )

    assert "--text-secondary: #575653;" in dash_tpl
    assert "--status-warning: #B45309;" in dash_tpl
    assert "#1B5E8A" in base_tpl
    assert "#595959" in base_tpl
    assert "#CBD5E1" in base_tpl

    # Verify mathematical WCAG 2.2 AA contrast ratios (>= 4.5:1 for normal text)
    text_pairs = [
        ("Light primary on canvas", "#1C1917", "#FAFAF9"),
        ("Light secondary on canvas", "#575653", "#FAFAF9"),
        ("Light secondary on card", "#575653", "#FFFFFF"),
        ("Light warning on card", "#B45309", "#FFFFFF"),
        ("Dark primary on canvas", "#ECE8E2", "#0D0E11"),
        ("Dark secondary on canvas", "#9A9895", "#0D0E11"),
        ("Dark secondary on card", "#9A9895", "#16171D"),
        ("Base link on white", "#1B5E8A", "#FFFFFF"),
        ("Base footer on white", "#595959", "#FFFFFF"),
        ("Base sidebar header on slate", "#CBD5E1", "#1E293B"),
    ]
    for label, fg, bg in text_pairs:
        ratio = _contrast_ratio(fg, bg)
        assert ratio >= 4.5, f"{label} ({fg} on {bg}) contrast {ratio:.2f}:1 < 4.5:1"

    # Non-text UI control border contrast (>= 3.0:1)
    assert _contrast_ratio("#767884", "#0D0E11") >= 3.0
    assert _contrast_ratio("#787774", "#FAFAF9") >= 3.0


def test_legal_draft_templates_exist_and_carry_disclaimer() -> None:
    """All four legal policy templates must exist under docs/legal/ with the DRAFT banner."""
    legal_dir = REPO_ROOT / "docs" / "legal"
    for name in ("privacy.md", "terms.md", "refunds.md", "cookies.md"):
        p = legal_dir / name
        assert p.is_file(), f"Missing legal template: {p}"
        text = p.read_text(encoding="utf-8")
        assert "DRAFT -- REQUIRES LEGAL REVIEW" in text


# ---------------------------------------------------------------------------
# 7. Repository Hygiene, Secret Scanning & Compiled Bundle Purity
# ---------------------------------------------------------------------------


def test_no_hardcoded_secrets_or_local_paths_in_source_and_bundles() -> None:
    """Tracked source code and compiled zip bundles must contain no secrets or machine-specific paths."""
    secret_patterns = [
        re.compile(r"sk-[A-Za-z0-9]{20,}"),
        re.compile(r"AIza[0-9A-Za-z_-]{35}"),
        re.compile(r"ghp_[A-Za-z0-9]{36}"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ]
    local_path_re = re.compile(r"(?:/Users/[a-zA-Z0-9._-]+/|/usr/local/google/home/[a-zA-Z0-9._-]+/|C:\\\\Users\\\\[a-zA-Z0-9._-]+\\\\)")

    scan_dirs = [
        REPO_ROOT / "pkde_plugin",
        REPO_ROOT / "tools" / "pkde",
        REPO_ROOT / "skills",
        REPO_ROOT / "templates",
        REPO_ROOT / "scripts",
    ]
    for base in scan_dirs:
        for path in base.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            if path.suffix not in {".py", ".md", ".html", ".json", ".yaml", ".yml", ".sh"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pat in secret_patterns:
                assert not pat.search(text), f"Potential secret pattern {pat.pattern} in {path}"
            assert not local_path_re.search(text), f"Local absolute machine path found in {path}"

    # Verify compiled zip bundles are present and clean of local paths
    zips = sorted((REPO_ROOT / "dist" / "skill-bundles").glob("*.zip"))
    assert len(zips) == 43
    for zpath in zips:
        with zipfile.ZipFile(zpath, "r") as zf:
            for member in zf.namelist():
                data = zf.read(member).decode("utf-8", errors="ignore")
                assert not local_path_re.search(data), f"Local path in {zpath.name}:{member}"
