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

"""Tests for the built-in Python/NumPy geometric pocket detector fallback in `pde pocket`."""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

from click.testing import CliRunner

os.environ.setdefault("PDE_NO_DIRTY_WARNING", "1")

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))

from pde.cli import cli  # noqa: E402
from pde.commands.docking import _compute_grid_box, _locate_pocket_atoms  # noqa: E402
from pde.core.context import init_project  # noqa: E402


def _write_synthetic_cavity_pdb(path: Path) -> None:
    """Write an experimental PDB structure forming a hollow hydrophobic shell around a cavity."""
    lines = [
        "HEADER    SYNTHETIC RECEPTOR                      08-OCT-26   1SYN",
        "EXPDTA    X-RAY DIFFRACTION",
    ]
    atom_serial = 1
    res_seq = 1
    # Build two concentric shells of atoms around origin (0, 0, 0) with radius 6.0 and 8.5 A,
    # leaving a central cavity of radius ~6.0 A (volume ~ 400-600 A^3) enclosed on all 6 axes.
    residues = ["LEU", "ILE", "VAL", "PHE", "ALA", "TRP", "MET", "TYR"]
    for r_shell in (6.0, 8.5):
        n_lat = 10
        n_lon = 18
        for i in range(n_lat):
            theta = math.pi * (i + 0.5) / n_lat
            for j in range(n_lon):
                phi = 2.0 * math.pi * j / n_lon
                x = r_shell * math.sin(theta) * math.cos(phi)
                y = r_shell * math.sin(theta) * math.sin(phi)
                z = r_shell * math.cos(theta)
                res_name = residues[(res_seq - 1) % len(residues)]
                lines.append(
                    f"ATOM  {atom_serial:5d}  CA  {res_name:>3s} A{res_seq:4d}    "
                    f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00           C  "
                )
                atom_serial += 1
                res_seq = (res_seq % 120) + 1
    lines.append("END")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_synthetic_cavity_cif(path: Path) -> None:
    """Write an mmCIF structure forming a hollow hydrophobic shell around a cavity."""
    lines = [
        "data_1SYN",
        "_exptl.method 'X-RAY DIFFRACTION'",
        "#",
        "loop_",
        "_atom_site.group_PDB",
        "_atom_site.id",
        "_atom_site.type_symbol",
        "_atom_site.label_atom_id",
        "_atom_site.label_comp_id",
        "_atom_site.auth_asym_id",
        "_atom_site.auth_seq_id",
        "_atom_site.Cartn_x",
        "_atom_site.Cartn_y",
        "_atom_site.Cartn_z",
    ]
    atom_serial = 1
    res_seq = 1
    residues = ["LEU", "ILE", "VAL", "PHE", "ALA", "TRP"]
    for r_shell in (6.0, 8.5):
        n_lat = 10
        n_lon = 18
        for i in range(n_lat):
            theta = math.pi * (i + 0.5) / n_lat
            for j in range(n_lon):
                phi = 2.0 * math.pi * j / n_lon
                x = r_shell * math.sin(theta) * math.cos(phi)
                y = r_shell * math.sin(theta) * math.sin(phi)
                z = r_shell * math.cos(theta)
                res_name = residues[(res_seq - 1) % len(residues)]
                lines.append(
                    f"ATOM {atom_serial} C CA {res_name} A {res_seq} "
                    f"{x:.3f} {y:.3f} {z:.3f}"
                )
                atom_serial += 1
                res_seq = (res_seq % 90) + 1
    lines.append("#")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_geometric_pocket_run_analyze_and_docking_grid_pdb(tmp_path: Path) -> None:
    """Test two-phase `pde pocket run --backend geometric` + `pde pocket analyze` and docking grid derivation on PDB."""
    proj_dir = init_project(tmp_path / "prog_pocket_pdb")
    runner = CliRunner()

    pdb_path = proj_dir / "raw" / "structures" / "1SYN.pdb"
    pdb_path.parent.mkdir(parents=True, exist_ok=True)
    _write_synthetic_cavity_pdb(pdb_path)

    # Phase 1: pde pocket run --backend geometric
    res_run = runner.invoke(
        cli,
        [
            "--project",
            str(proj_dir),
            "pocket",
            "run",
            str(pdb_path),
            "--backend",
            "geometric",
            "--json",
        ],
    )
    assert res_run.exit_code == 0, res_run.output
    run_summary = json.loads(res_run.output)
    assert run_summary["backend"] == "geometric"
    assert run_summary["n_pockets"] >= 1

    pockets_json_path = proj_dir / "raw" / "structures" / "1SYN.pockets.json"
    meta_json_path = proj_dir / "raw" / "structures" / "1SYN.pockets.meta.json"
    fpocket_tree = proj_dir / "raw" / "structures" / "1SYN_fpocket"
    assert pockets_json_path.is_file()
    assert meta_json_path.is_file()
    assert (fpocket_tree / "1SYN_info.txt").is_file()
    assert (fpocket_tree / "pockets" / "pocket1_atm.pdb").is_file()

    pockets_record = json.loads(pockets_json_path.read_text(encoding="utf-8"))
    assert pockets_record["backend"] == "geometric"
    assert pockets_record["n_pockets"] >= 1
    assert pockets_record["pockets"][0]["druggability_score"] >= 0.5

    meta_doc = json.loads(meta_json_path.read_text(encoding="utf-8"))
    meta_relays = {r["code"] for r in meta_doc.get("mandatory_relays", [])}
    assert "pocket.geometric_fallback_backend" in meta_relays

    # Phase 2A: pde pocket analyze (whole structure)
    res_analyze = runner.invoke(
        cli,
        [
            "--project",
            str(proj_dir),
            "pocket",
            "analyze",
            str(pockets_json_path),
            "--json",
        ],
    )
    assert res_analyze.exit_code == 0, res_analyze.output
    analysis = json.loads(res_analyze.output)
    assert analysis["assessment"]["verdict"] in ("druggable-pocket-present", "borderline")
    analysis_relays = {r["code"] for r in analysis.get("mandatory_relays", [])}
    assert "pocket.geometric_fallback_backend" in analysis_relays

    # Phase 2B: pde pocket analyze --near (site-specific)
    lining = pockets_record["pockets"][0]["residues"]
    assert len(lining) >= 1
    first_res = f"{lining[0]['chain']}:{lining[0]['resnum']}"
    res_near = runner.invoke(
        cli,
        [
            "--project",
            str(proj_dir),
            "pocket",
            "analyze",
            str(pockets_json_path),
            "--near",
            first_res,
            "--overwrite",
            "--json",
        ],
    )
    assert res_near.exit_code == 0, res_near.output
    near_analysis = json.loads(res_near.output)
    assert near_analysis["assessment"]["verdict"] in ("site-druggable", "site-borderline")

    # Downstream docking grid-box compatibility
    pocket_atm_file = _locate_pocket_atoms(fpocket_tree, rank=1)
    center, size = _compute_grid_box(pocket_atm_file, padding=4.0)
    assert abs(center[0]) < 3.0
    assert abs(center[1]) < 3.0
    assert abs(center[2]) < 3.0
    assert size[0] > 5.0


def test_geometric_pocket_auto_fallback_cif(tmp_path: Path) -> None:
    """Test two-phase `pde pocket run --backend auto` + `pde pocket analyze` and docking grid derivation on mmCIF."""
    proj_dir = init_project(tmp_path / "prog_pocket_cif")
    runner = CliRunner()

    cif_path = proj_dir / "raw" / "structures" / "1SYN.cif"
    cif_path.parent.mkdir(parents=True, exist_ok=True)
    _write_synthetic_cavity_cif(cif_path)

    # Phase 1: pde pocket run --backend auto
    res_run = runner.invoke(
        cli,
        [
            "--project",
            str(proj_dir),
            "pocket",
            "run",
            str(cif_path),
            "--backend",
            "auto",
            "--json",
        ],
    )
    assert res_run.exit_code == 0, res_run.output
    run_summary = json.loads(res_run.output)
    assert run_summary["n_pockets"] >= 1

    pockets_json_path = proj_dir / "raw" / "structures" / "1SYN.pockets.json"
    fpocket_tree = proj_dir / "raw" / "structures" / "1SYN_fpocket"
    # Phase 2: pde pocket analyze
    res_analyze = runner.invoke(
        cli,
        [
            "--project",
            str(proj_dir),
            "pocket",
            "analyze",
            str(pockets_json_path),
            "--json",
        ],
    )
    assert res_analyze.exit_code == 0, res_analyze.output

    # Downstream docking grid-box compatibility on CIF
    pocket_atm_file = _locate_pocket_atoms(fpocket_tree, rank=1)
    assert pocket_atm_file.suffix == ".cif"
    center, size = _compute_grid_box(pocket_atm_file, padding=4.0)
    assert size[0] > 5.0
    assert size[1] > 5.0
    assert size[2] > 5.0


def test_relays_registry_includes_geometric_fallback() -> None:
    """Verify `pde relays --json` attributes `pocket.geometric_fallback_backend` to `pocket run`."""
    runner = CliRunner()
    res = runner.invoke(cli, ["relays", "--json"])
    assert res.exit_code == 0, res.output
    relays_doc = json.loads(res.output)
    assert "pocket.geometric_fallback_backend" in relays_doc
    assert "pocket run" in relays_doc["pocket.geometric_fallback_backend"]["emitted_by"]
