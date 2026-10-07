#!/usr/bin/env python3
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

"""Target Compiler (`pde_plugin/build_targets.py`).

Compiles the unified PDE skills (`skills/*`) and 22 specialist role templates
(`templates/*`) into three ready-to-run targets:
1. Sanitized and frontmatter-validated `skills/*/SKILL.md` (all 43 skills).
2. Agent Plugin bundle (`.agents/plugins/pharmakon-discovery-engine/` + `.agents/plugins.json`).
3. Packaged `.zip` Skill Bundles (`dist/skill-bundles/*.zip`).
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))

from pde.commands.dashboard import _load_roles_catalog  # noqa: E402
from pde_plugin.sync_skills_to_registry import package_all_skills_to_dir  # noqa: E402

MISSING_FRONTMATTER_METADATA: dict[str, dict[str, Any]] = {
    "artifact-conventions": {
        "name": "artifact-conventions",
        "description": (
            "Defines the 4-layer PDE artifact hierarchy (Layer 0 raw/ + .meta.json + "
            ".analysis.json, Layer 1 findings/, Layer 2 program-state/, Layer 4 executive/), "
            "inline {source: ...} provenance tags, mandatory relays, and 10-check validation rules."
        ),
        "metadata": {
            "display_name": "PDE Artifact Conventions & 4-Layer Hierarchy",
        },
    },
    "competitive-differentiation": {
        "name": "competitive-differentiation",
        "description": (
            "Evaluates competitive clinical pipelines, mechanism-of-action differentiation, "
            "patent/trial density, and target product profile positioning using pde trials, "
            "pde patent, and pde differentiation."
        ),
        "metadata": {
            "display_name": "Competitive Landscape & Clinical Differentiation Analysis",
        },
    },
    "program-state-management": {
        "name": "program-state-management",
        "description": (
            "Maintains Layer 2 program-state artifacts (active-series.md, liability-tracker.md, "
            "decision-log.md, open-questions.md) and Layer 4 executive synthesis across "
            "multi-cycle drug discovery campaigns."
        ),
        "metadata": {
            "display_name": "PDE Layer 2 Program State & Decision Log Management",
        },
    },
    "site-generation": {
        "name": "site-generation",
        "description": (
            "Builds and publishes the PDE static dossier site (pde site build) and the "
            "unified PDE interactive scientific dashboard (pde dashboard build --standalone)."
        ),
        "metadata": {
            "display_name": "PDE Static Dossier Site & Interactive Dashboard Publication",
        },
    },
}


def _clean_single_line(value: str) -> str:
    """Collapse multi-line text and normalize Unicode punctuation to single-line ASCII."""
    cleaned = (
        str(value)
        .replace("\u2014", "--")
        .replace("\u2013", "-")
        .replace("\u2019", "'")
        .replace("\u00a7", "Section ")
        .replace("\u2192", "->")
        .replace("\u2026", "...")
        .replace('"', "'")
    )
    return " ".join(cleaned.split())


def _format_frontmatter_yaml(fm_data: dict[str, Any]) -> str:
    """Format skill YAML frontmatter with guaranteed single-line name and description."""
    name_val = _clean_single_line(str(fm_data.get("name", "")))
    desc_val = _clean_single_line(str(fm_data.get("description", "")))
    lines = [
        f"name: {name_val}",
        f"description: {json.dumps(desc_val)}",
    ]
    extra = {
        k: v
        for k, v in fm_data.items()
        if k not in ("name", "description") and v is not None
    }
    if extra:
        extra_yaml = yaml.safe_dump(extra, sort_keys=False, width=10000).strip()
        lines.append(extra_yaml)
    return "\n".join(lines)


def _sanitize_single_skill_md(skill_md: Path, default_skill_name: str) -> bool:
    """Ensure a single SKILL.md file has normalized single-line YAML frontmatter."""
    text = skill_md.read_text(encoding="utf-8")
    original_text = text

    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not fm_match:
        meta = dict(MISSING_FRONTMATTER_METADATA.get(default_skill_name) or {})
        if not meta:
            lines = [
                ln.strip()
                for ln in text.splitlines()
                if ln.strip() and not ln.strip().startswith("#")
            ]
            desc = (
                lines[0][:300]
                if lines
                else f"PDE scientific skill for {default_skill_name}."
            )
            meta = {
                "name": default_skill_name,
                "description": desc,
                "metadata": {
                    "display_name": default_skill_name.replace("-", " ").title(),
                },
            }
        fm_yaml = _format_frontmatter_yaml(meta)
        text = f"---\n{fm_yaml}\n---\n\n{text.lstrip()}"
    else:
        fm_data = yaml.safe_load(fm_match.group(1)) or {}
        if not fm_data.get("name"):
            fm_data["name"] = default_skill_name
        if not fm_data.get("description"):
            meta = MISSING_FRONTMATTER_METADATA.get(default_skill_name, {})
            fm_data["description"] = meta.get(
                "description", f"PDE scientific skill for {default_skill_name}."
            )
        if "display_name" in fm_data:
            disp = fm_data.pop("display_name")
            meta_dict = dict(fm_data.get("metadata") or {})
            meta_dict["display_name"] = _clean_single_line(str(disp))
            fm_data["metadata"] = meta_dict
        elif isinstance(fm_data.get("metadata"), dict) and "display_name" in fm_data["metadata"]:
            meta_dict = dict(fm_data["metadata"])
            meta_dict["display_name"] = _clean_single_line(str(meta_dict["display_name"]))
            fm_data["metadata"] = meta_dict

        body = text[fm_match.end() :]
        fm_yaml = _format_frontmatter_yaml(fm_data)
        text = f"---\n{fm_yaml}\n---\n\n{body.lstrip()}"

    if text != original_text:
        skill_md.write_text(text, encoding="utf-8")
        return True
    return False


def sanitize_and_fix_skills(skills_dir: Path) -> list[str]:
    """Ensure all skills have valid single-line YAML frontmatter and portable env.sh paths."""
    updated_skills: list[str] = []

    root_skill_md = skills_dir.parent / "SKILL.md"
    if root_skill_md.is_file():
        _sanitize_single_skill_md(root_skill_md, "pharmakon-discovery-engine")

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue

        skill_name = skill_dir.name
        _sanitize_single_skill_md(skill_md, skill_name)
        updated_skills.append(skill_name)

    return updated_skills


def build_agent_plugin(repo_root: Path) -> dict[str, Any]:
    """Generate .agents/plugins.json and .agents/plugins/pharmakon-discovery-engine/."""
    agents_root = repo_root / ".agents"
    plugin_root = agents_root / "plugins" / "pharmakon-discovery-engine"
    plugin_agents_dir = plugin_root / "agents"
    plugin_rules_dir = plugin_root / "rules"
    plugin_skills_dir = plugin_root / "skills"

    if plugin_skills_dir.exists():
        shutil.rmtree(plugin_skills_dir)
    if plugin_agents_dir.exists():
        shutil.rmtree(plugin_agents_dir)

    plugin_agents_dir.mkdir(parents=True, exist_ok=True)
    plugin_rules_dir.mkdir(parents=True, exist_ok=True)
    plugin_skills_dir.mkdir(parents=True, exist_ok=True)

    # 1. Write .agents/plugins.json
    plugins_json_path = agents_root / "plugins.json"
    plugins_json = {
        "plugins": [
            {
                "name": "pharmakon-discovery-engine",
                "path": ".agents/plugins/pharmakon-discovery-engine",
                "enabled": True,
            }
        ]
    }
    plugins_json_path.write_text(
        json.dumps(plugins_json, indent=2) + "\n", encoding="utf-8"
    )

    # 2. Write .agents/plugins/pharmakon-discovery-engine/plugin.json
    plugin_manifest = {
        "name": "pharmakon-discovery-engine",
        "displayName": "Pharmakon Discovery Engine (PDE) Multi-Agent Harness",
        "version": "0.3.0",
        "description": (
            "Full-spectrum pre-clinical drug discovery harness with 43 scientific "
            "skills, 22 specialist subagents, 10-check mechanical validation, and "
            "the unified PDE interactive scientific dashboard."
        ),
        "mcpServers": "./mcp_config.json",
        "skills": "./skills",
        "agents": "./agents",
        "rules": "./rules",
    }
    (plugin_root / "plugin.json").write_text(
        json.dumps(plugin_manifest, indent=2) + "\n", encoding="utf-8"
    )

    # 3. Write .agents/plugins/pharmakon-discovery-engine/mcp_config.json
    mcp_config = {
        "mcpServers": {
            "pde-engine": {
                "command": ".venv/bin/python",
                "args": ["-m", "pde_plugin.mcp_server"],
                "cwd": ".",
                "env": {
                    "PDE_ROOT": ".",
                    "PYTHONPATH": ".:./tools:./tools/vendor/hypex",
                },
            }
        }
    }
    (plugin_root / "mcp_config.json").write_text(
        json.dumps(mcp_config, indent=2) + "\n", encoding="utf-8"
    )

    # 4. Write .agents/plugins/pharmakon-discovery-engine/rules/pde-scientific-integrity.md
    rule_content = """---
name: pde-scientific-integrity
description: "Mandatory scientific integrity, two-phase tool execution, provenance sidecars, and relay rules for PDE."
trigger: always_on
---

# PDE Scientific Integrity & Provenance Rules

1. **Two-Phase Execution Invariant**: Every `pde` domain tool command (Phase 1: `fetch`/`run`/`compute`/`predict`) MUST be followed immediately by its corresponding `pde <tool> analyze` (Phase 2) command before running any other tool.
2. **Never Hand-Craft Layer 0 JSON**: All files in `raw/` must be produced by `pde` CLI commands with matching `.meta.json` SHA-256 provenance sidecars and `.analysis.json` interpretation records.
3. **Mandatory Relays & Inline Source Citations**: Every code in `mandatory_relays` from `.analysis.json` must be surfaced verbatim in Layer 1 Markdown reports (`**Relay: \\`<code>\\`**`), and every quantitative claim must cite its Layer 0 JSON path (`{source: raw/<category>/<file>#$.path}`).
4. **Always Update the Interactive Dashboard**: After completing a scientific query or Work Order cycle, run `./bin/pde dashboard build --standalone` (or `pde_render_dashboard`) so `dashboard.html` reflects the latest multi-agent lineage graph and 14 scientific viewers.
"""
    (plugin_rules_dir / "pde-scientific-integrity.md").write_text(
        rule_content, encoding="utf-8"
    )

    # 5. Sync all core skills (and optional user extension skills) into .agents/plugins/pharmakon-discovery-engine/skills/
    src_skills_dir = repo_root / "skills"
    copied_skills: list[str] = []
    for sdir in sorted(src_skills_dir.iterdir()):
        if not sdir.is_dir() or not (sdir / "SKILL.md").is_file():
            continue
        dest_sdir = plugin_skills_dir / sdir.name
        shutil.copytree(sdir, dest_sdir)
        copied_skills.append(sdir.name)

    ext_skills_dir = repo_root / "extensions" / "skills"
    if ext_skills_dir.is_dir():
        for sdir in sorted(ext_skills_dir.iterdir()):
            if not sdir.is_dir() or not (sdir / "SKILL.md").is_file():
                continue
            _sanitize_single_skill_md(sdir / "SKILL.md", sdir.name)
            dest_sdir = plugin_skills_dir / sdir.name
            if dest_sdir.exists():
                shutil.rmtree(dest_sdir)
            shutil.copytree(sdir, dest_sdir)
            if sdir.name not in copied_skills:
                copied_skills.append(sdir.name)

    # 6. Compile all 22 templates/<role>/ into .agents/plugins/pharmakon-discovery-engine/agents/pde-<role>.md
    roles_catalog = _load_roles_catalog()
    ext_grants_path = repo_root / "extensions" / "role-grants.yaml"
    if ext_grants_path.is_file():
        ext_grants = yaml.safe_load(ext_grants_path.read_text(encoding="utf-8")) or {}
        if isinstance(ext_grants, dict):
            for r_name, extra_skills in ext_grants.items():
                if r_name in roles_catalog and isinstance(extra_skills, list):
                    existing = list(roles_catalog[r_name].get("skills", []))
                    for sk in extra_skills:
                        if isinstance(sk, str) and sk not in existing:
                            existing.append(sk)
                    roles_catalog[r_name]["skills"] = existing

    templates_dir = repo_root / "templates"
    generated_agents: list[str] = []

    for role_name, role_info in sorted(roles_catalog.items()):
        role_dir = templates_dir / role_name
        sys_prompt_path = role_dir / "system-prompt.md"
        agents_md_path = role_dir / "agents.md"

        sys_prompt_txt = (
            sys_prompt_path.read_text(encoding="utf-8")
            if sys_prompt_path.is_file()
            else ""
        )
        agents_md_txt = (
            agents_md_path.read_text(encoding="utf-8")
            if agents_md_path.is_file()
            else ""
        )

        subagent_name = f"pde-{role_name}"
        description = _clean_single_line(
            str(role_info.get("description") or role_info["display_name"]).strip()
        )
        assigned_skills = role_info.get("skills", [])

        frontmatter = {
            "name": subagent_name,
            "description": f"{role_info['display_name']} -- {description}",
            "mainAgent": role_name in ("science-program-lead", "research-operations-controller"),
            "subagent": True,
            "model": "inherit",
            "tools": [
                "run_command",
                "view_file",
                "write_to_file",
                "replace_file_content",
            ],
            "skills": assigned_skills,
        }
        fm_str = yaml.safe_dump(frontmatter, sort_keys=False, width=10000).strip()

        skills_bullet_list = "\n".join(
            f"- `{sk}` (`skills/{sk}/SKILL.md`)" for sk in assigned_skills
        )

        agent_md = (
            f"---\n{fm_str}\n---\n\n"
            f"# {role_info['display_name']} (`{subagent_name}`)\n\n"
            f"- **Role Category**: {role_info['category']}\n"
            f"- **Portable Environment**: `source \"${{PDE_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}}/bin/env.sh\"`\n\n"
            f"## Assigned Skill Lanes (`templates/{role_name}/agent.yaml`)\n"
            f"{skills_bullet_list}\n\n"
            f"## Harness Execution Notes\n"
            f"- Execute `pde` CLI commands via `./bin/pde <group> <command> --json` or `pde_exec`.\n"
            f"- Return your structured completion summary directly in your final response after verifying deliverables with `./bin/pde validate check <WO-ID> --dry-run`.\n\n"
            f"---\n\n"
            f"## System Prompt (`system-prompt.md`)\n\n"
            f"{sys_prompt_txt.strip()}\n\n"
            f"---\n\n"
            f"## Operational Instructions (`agents.md`)\n\n"
            f"{agents_md_txt.strip()}\n"
        )

        out_path = plugin_agents_dir / f"{subagent_name}.md"
        out_path.write_text(agent_md, encoding="utf-8")
        generated_agents.append(subagent_name)

    return {
        "plugins_json": str(plugins_json_path.relative_to(repo_root)),
        "plugin_root": str(plugin_root.relative_to(repo_root)),
        "skills_copied": len(copied_skills),
        "agents_generated": len(generated_agents),
        "agent_names": generated_agents,
    }


def build_all_targets(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Compile all skills, agent plugin files, and packaged .zip skill bundles."""
    skills_dir = repo_root / "skills"
    skill_bundles_dir = repo_root / "dist" / "skill-bundles"
    if skill_bundles_dir.exists():
        shutil.rmtree(skill_bundles_dir)

    sanitized = sanitize_and_fix_skills(skills_dir)
    plugin_result = build_agent_plugin(repo_root)
    packaged = package_all_skills_to_dir(skills_dir, skill_bundles_dir)

    return {
        "sanitized_skills_count": len(sanitized),
        "agent_plugin": plugin_result,
        "skill_zip_bundles_count": len(packaged),
        "skill_bundles_dir": str(skill_bundles_dir.relative_to(repo_root)),
    }


def main() -> int:
    summary = build_all_targets(REPO_ROOT)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
