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

"""Tests for Target Compilation: 43 Skills, Agent Plugin (.agents/plugins/pharmakon-discovery-engine/), and Skill Bundles."""

from __future__ import annotations

import json
import re
import zipfile

import yaml

from pde.commands.dashboard import _load_roles_catalog
from pde_plugin.build_targets import REPO_ROOT, build_all_targets
from pde_plugin.sync_skills_to_registry import discover_skills, parse_frontmatter


def _assert_valid_single_line_frontmatter(raw_md: str, expected_name: str, label: str) -> None:
    """Verify both full YAML parsers and single-line regex parsers extract identical name and description."""
    fm_match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", raw_md, re.DOTALL)
    assert fm_match is not None, f"{label}: missing YAML frontmatter block"
    fm_block = fm_match.group(1)

    parsed_yaml = yaml.safe_load(fm_block)
    assert isinstance(parsed_yaml, dict), f"{label}: frontmatter is not a YAML mapping"
    fm = parse_frontmatter(raw_md)
    assert fm.get("name") == expected_name, f"{label}: name mismatch ({fm.get('name')!r} != {expected_name!r})"
    desc = str(fm.get("description", "")).strip()
    assert len(desc) >= 20, f"{label}: description too short ({desc!r})"
    assert expected_name.isascii(), f"{label}: non-ASCII name"
    assert desc.isascii(), f"{label}: non-ASCII description"

    # Also verify simple line-by-line regex harness parsers extract the exact same single-line values
    name_line_match = re.search(r"^name:\s*(.+)$", fm_block, re.MULTILINE)
    desc_line_match = re.search(r"^description:\s*(.+)$", fm_block, re.MULTILINE)
    assert name_line_match is not None, f"{label}: missing single-line name field"
    assert desc_line_match is not None, f"{label}: missing single-line description field"

    line_name = name_line_match.group(1).strip().strip('"').strip("'")
    line_desc = desc_line_match.group(1).strip().strip('"').strip("'")
    assert line_name == expected_name, f"{label}: line-parsed name {line_name!r} != {expected_name!r}"
    assert line_desc == desc, f"{label}: line-parsed description truncated or mismatched"


def test_all_43_skills_load_and_pass_frontmatter_discovery() -> None:
    root_skill = REPO_ROOT / "SKILL.md"
    assert root_skill.is_file()
    _assert_valid_single_line_frontmatter(
        root_skill.read_text(encoding="utf-8"),
        "pharmakon-discovery-engine",
        "SKILL.md",
    )

    skills_dir = REPO_ROOT / "skills"
    skill_dirs = [
        p for p in sorted(skills_dir.iterdir()) if p.is_dir() and (p / "SKILL.md").is_file()
    ]
    assert len(skill_dirs) == 43

    for sdir in skill_dirs:
        raw_md = (sdir / "SKILL.md").read_text(encoding="utf-8")
        _assert_valid_single_line_frontmatter(raw_md, sdir.name, f"skills/{sdir.name}/SKILL.md")

    discovered = discover_skills(skills_dir)
    assert len(discovered) == 43


def test_agent_plugin_and_22_subagents_generated() -> None:
    summary = build_all_targets(REPO_ROOT)
    assert summary["sanitized_skills_count"] == 43
    assert summary["skill_zip_bundles_count"] == 43

    plugins_json = REPO_ROOT / ".agents" / "plugins.json"
    assert plugins_json.is_file()
    pdata = json.loads(plugins_json.read_text(encoding="utf-8"))
    assert pdata["plugins"][0]["name"] == "pharmakon-discovery-engine"
    assert pdata["plugins"][0]["enabled"] is True

    plugin_dir = REPO_ROOT / ".agents" / "plugins" / "pharmakon-discovery-engine"
    assert (plugin_dir / "plugin.json").is_file()
    assert (plugin_dir / "mcp_config.json").is_file()
    assert (plugin_dir / "rules" / "pde-scientific-integrity.md").is_file()

    plugin_skill_dirs = [
        p for p in sorted((plugin_dir / "skills").iterdir()) if p.is_dir() and (p / "SKILL.md").is_file()
    ]
    assert len(plugin_skill_dirs) == 43
    for psdir in plugin_skill_dirs:
        _assert_valid_single_line_frontmatter(
            (psdir / "SKILL.md").read_text(encoding="utf-8"),
            psdir.name,
            f".agents/plugins/pharmakon-discovery-engine/skills/{psdir.name}/SKILL.md",
        )

    agent_files = sorted((plugin_dir / "agents").glob("pde-*.md"))
    assert len(agent_files) == 22

    catalog = _load_roles_catalog()
    for role_name, role_info in catalog.items():
        agent_md_path = plugin_dir / "agents" / f"pde-{role_name}.md"
        assert agent_md_path.is_file(), f"Missing subagent file {agent_md_path}"
        content = agent_md_path.read_text(encoding="utf-8")
        _assert_valid_single_line_frontmatter(content, f"pde-{role_name}", str(agent_md_path))
        for sk in role_info["skills"]:
            assert sk in content


def test_skill_zip_bundles_valid() -> None:
    bundles_dir = REPO_ROOT / "dist" / "skill-bundles"
    zips = sorted(bundles_dir.glob("*.zip"))
    assert len(zips) == 43
    for zpath in zips:
        with zipfile.ZipFile(zpath, "r") as zf:
            names = zf.namelist()
            assert "SKILL.md" in names, f"{zpath.name} missing SKILL.md"
            raw_md = zf.read("SKILL.md").decode("utf-8")
            _assert_valid_single_line_frontmatter(raw_md, zpath.stem, f"{zpath.name}:SKILL.md")

    # Confirm the two primary skills contain their executable scripts
    with zipfile.ZipFile(bundles_dir / "pharmakon-discovery-engine.zip", "r") as zf:
        pde_names = zf.namelist()
        assert "scripts/start_live_session.py" in pde_names
        assert "scripts/pde_runner.py" in pde_names
        assert "scripts/dispatch_workorder.py" in pde_names

    with zipfile.ZipFile(bundles_dir / "pde-dashboard.zip", "r") as zf:
        dash_names = zf.namelist()
        assert "scripts/render_dashboard.py" in dash_names
