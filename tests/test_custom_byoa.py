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

"""End-to-end tests for the Bring-Your-Own-Algorithm (BYOA) & Private Data Framework."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from click.testing import CliRunner

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))

from pde.cli import cli, load_extension_commands  # noqa: E402
from pde.core.context import init_project  # noqa: E402


def test_byoa_example_files_exist() -> None:
    """Verify the reference BYOA sample data, algorithm script, and skill exist."""
    byoa_dir = REPO_ROOT / "examples" / "byoa"
    assert (byoa_dir / "sample_private_compounds.json").is_file()
    assert (byoa_dir / "sample_private_assay.csv").is_file()
    assert (byoa_dir / "proprietary_cns_mpo_scorer.py").is_file()
    assert (byoa_dir / "skills" / "proprietary-cns-scorer" / "SKILL.md").is_file()


def test_custom_ingest_and_analyze_csv(tmp_path: Path) -> None:
    """Test two-phase private CSV ingestion and offline evaluation."""
    proj_dir = init_project(tmp_path / "prog_csv")
    runner = CliRunner()
    csv_path = REPO_ROOT / "examples" / "byoa" / "sample_private_assay.csv"

    # Phase 1A: Ingest CSV
    res1 = runner.invoke(
        cli,
        [
            "--project",
            str(proj_dir),
            "custom",
            "ingest",
            str(csv_path),
            "--class",
            "bioactivity",
            "--name",
            "internal-assay",
            "--id-col",
            "compound_id",
            "--json",
        ],
    )
    assert res1.exit_code == 0, res1.output
    out1 = json.loads(res1.output)
    assert out1["n_records"] == 6

    artifact_path = proj_dir / "raw" / "bioactivity" / "internal-assay.custom.json"
    meta_path = proj_dir / "raw" / "bioactivity" / "internal-assay.custom.meta.json"
    assert artifact_path.is_file()
    assert meta_path.is_file()

    meta_doc = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta_doc["tool"] == "custom"
    assert meta_doc["subcommand"] == "ingest"
    assert len(meta_doc["outputs"]) == 1

    # Phase 2: Analyze kp_uu_brain offline
    res2 = runner.invoke(
        cli,
        [
            "--project",
            str(proj_dir),
            "custom",
            "analyze",
            str(artifact_path),
            "--metric",
            "kp_uu_brain",
            "--id-field",
            "compound_id",
            "--pass-cutoff",
            "0.50",
            "--warn-cutoff",
            "0.25",
            "--direction",
            "higher",
            "--json",
        ],
    )
    assert res2.exit_code == 0, res2.output
    out2 = json.loads(res2.output)
    assert out2["metrics"]["n_evaluated"] == 6
    assert out2["metrics"]["pass_count"] == 3  # CMPD-901 (0.68), CMPD-902 (0.54), CMPD-906 (0.74)
    assert out2["metrics"]["warn_count"] == 1  # CMPD-903 (0.35)
    assert out2["metrics"]["fail_count"] == 2  # CMPD-904 (0.24), CMPD-905 (0.08)
    assert out2["assessment"]["top_candidate"] == "CMPD-906"

    relay_codes = {r["code"] for r in out2.get("mandatory_relays", [])}
    assert "custom.uncalibrated_threshold" in relay_codes
    assert "custom.liability_flagged" in relay_codes


def test_custom_run_and_analyze_proprietary_algorithm(tmp_path: Path) -> None:
    """Test two-phase proprietary Python algorithm execution and offline analysis."""
    proj_dir = init_project(tmp_path / "prog_byoa")
    runner = CliRunner()
    input_json = REPO_ROOT / "examples" / "byoa" / "sample_private_compounds.json"
    script_py = REPO_ROOT / "examples" / "byoa" / "proprietary_cns_mpo_scorer.py"

    # Phase 1B: Run proprietary algorithm
    cmd_str = f"{sys.executable} {script_py} --input {{input}} --output {{output}}"
    res1 = runner.invoke(
        cli,
        [
            "--project",
            str(proj_dir),
            "custom",
            "run",
            "--cmd",
            cmd_str,
            "--input",
            str(input_json),
            "--class",
            "mpo",
            "--name",
            "cns-lead-series",
            "--algorithm-id",
            "proprietary-cns-bbb-mpo@1.2.0",
            "--json",
        ],
    )
    assert res1.exit_code == 0, res1.output
    out1 = json.loads(res1.output)
    assert out1["n_records"] == 6
    assert out1["algorithm_id"] == "proprietary-cns-bbb-mpo@1.2.0"
    assert out1["algorithm_sha256"] is not None

    artifact_path = proj_dir / "raw" / "mpo" / "cns-lead-series.custom.json"
    meta_path = proj_dir / "raw" / "mpo" / "cns-lead-series.custom.meta.json"
    assert artifact_path.is_file()
    assert meta_path.is_file()

    # Phase 2: Analyze cns_bbb_score offline
    res2 = runner.invoke(
        cli,
        [
            "--project",
            str(proj_dir),
            "custom",
            "analyze",
            str(artifact_path),
            "--metric",
            "cns_bbb_score",
            "--id-field",
            "compound_id",
            "--json",
        ],
    )
    assert res2.exit_code == 0, res2.output
    out2 = json.loads(res2.output)
    assert out2["metrics"]["metric_name"] == "cns_bbb_score"
    assert out2["metrics"]["n_evaluated"] == 6
    assert out2["assessment"]["top_candidate"] == "CMPD-906"

    relay_codes = {r["code"] for r in out2.get("mandatory_relays", [])}
    assert "custom.external_algorithm_caveat" in relay_codes
    assert "custom.uncalibrated_threshold" in relay_codes
    assert "custom.liability_flagged" in relay_codes

    analysis_path = proj_dir / "raw" / "mpo" / "cns-lead-series.custom.analysis.json"
    assert analysis_path.is_file()


def test_relays_enumeration_has_no_orphans() -> None:
    """Verify `pde relays --json` attributes all custom relays with zero orphans."""
    runner = CliRunner()
    res = runner.invoke(cli, ["relays", "--json"])
    assert res.exit_code == 0, res.output
    relays_doc = json.loads(res.output)
    for code in (
        "custom.external_algorithm_caveat",
        "custom.uncalibrated_threshold",
        "custom.liability_flagged",
    ):
        assert code in relays_doc
        assert len(relays_doc[code]["emitted_by"]) >= 1


def test_dynamic_extension_command_loader(tmp_path: Path) -> None:
    """Verify project-local Click extensions load dynamically and get Phase 2 guarded."""
    ext_dir = tmp_path / "commands"
    ext_dir.mkdir(parents=True)
    plugin_file = ext_dir / "private_qsar.py"
    plugin_file.write_text(
        """import click
from pde.common import PDEGroup

@click.group(cls=PDEGroup, name="private-qsar")
def command():
    \"\"\"Private QSAR extension.\"\"\"

@command.command("analyze")
def analyze():
    \"\"\"Phase 2 analyze command.\"\"\"
    click.echo("ok")
""",
        encoding="utf-8",
    )

    loaded = load_extension_commands(cli, extra_dirs=[ext_dir])
    assert "private-qsar" in loaded
    ext_group = cli.commands["private-qsar"]
    analyze_cmd = ext_group.commands["analyze"]
    assert getattr(analyze_cmd.callback, "_phase_two_guarded", False) is True
    param_names = {p.name for p in analyze_cmd.params}
    assert "overwrite" in param_names
    assert "overwrite_cross_wo" in param_names
    # Clean up temporary command from global cli group
    cli.commands.pop("private-qsar", None)
