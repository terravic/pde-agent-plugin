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

"""Differential and mutation verification tests for domain computation and SHA-256 provenance.

Each test runs domain tools against distinct inputs (or mutates an artifact byte)
and verifies that the mathematical outputs change deterministically as dictated
by chemistry, pharmacokinetics, 3D geometry, Elo math, and SHA-256 cryptography.
"""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

from pkde_plugin.tool_bridge import (
    REPO_ROOT,
    pkde_dispatch_workorder,
    pkde_exec,
    pkde_validate_and_gate,
)
from tests.test_pocket_geometric import _write_synthetic_cavity_pdb


def test_rdkit_compound_profile_differential_math(tmp_path: Path) -> None:
    """Prove RDKit computes real molecular descriptors that change deterministically with SMILES."""
    ws = tmp_path / "ws-rdkit-diff"

    # Input A: Aspirin (MW = 180.16, 0 Lipinski violations)
    r_asp_p1 = pkde_exec(
        'compound profile "CC(=O)Oc1ccccc1C(=O)O" --name aspirin --json',
        project_dir=str(ws),
        auto_refresh_dashboard=False,
    )
    assert r_asp_p1["ok"] is True, r_asp_p1
    r_asp_p2 = pkde_exec(
        "compound analyze aspirin --json",
        project_dir=str(ws),
        auto_refresh_dashboard=False,
    )
    assert r_asp_p2["ok"] is True, r_asp_p2

    # Input B: Heavy lipophilic lipopeptide (MW > 650 Da, LogP > 6, multiple Lipinski/Veber violations)
    heavy_smiles = "CCCCCCCCCCCCCCCC(=O)NC(Cc1ccccc1)C(=O)NC(Cc2ccccc2)C(=O)NC(Cc3ccccc3)C(=O)O"
    r_hvy_p1 = pkde_exec(
        f'compound profile "{heavy_smiles}" --name heavy_lipopeptide --json',
        project_dir=str(ws),
        auto_refresh_dashboard=False,
    )
    assert r_hvy_p1["ok"] is True, r_hvy_p1
    r_hvy_p2 = pkde_exec(
        "compound analyze heavy_lipopeptide --json",
        project_dir=str(ws),
        auto_refresh_dashboard=False,
    )
    assert r_hvy_p2["ok"] is True, r_hvy_p2

    asp_desc = json.loads(
        (ws / "raw/compounds/aspirin.descriptors.json").read_text(encoding="utf-8")
    )["descriptors"]
    hvy_desc = json.loads(
        (ws / "raw/compounds/heavy_lipopeptide.descriptors.json").read_text(
            encoding="utf-8"
        )
    )["descriptors"]

    assert math.isclose(asp_desc["molecular_weight"], 180.16, abs_tol=0.1)
    assert asp_desc["hbd"] == 1
    assert asp_desc["hba"] == 3

    assert hvy_desc["molecular_weight"] > 650.0
    assert hvy_desc["logp"] > 5.5
    assert hvy_desc["rotatable_bonds"] > 15
    assert hvy_desc["molecular_weight"] > asp_desc["molecular_weight"] * 3.5

    asp_analysis = r_asp_p2["data"]
    hvy_analysis = r_hvy_p2["data"]
    assert asp_analysis["metrics"]["n_lipinski_violations"] == 0
    assert hvy_analysis["metrics"]["n_lipinski_violations"] >= 2
    assert asp_analysis["assessment"]["verdict"] != hvy_analysis["assessment"]["verdict"]


def test_pk_nca_trapezoidal_integration_scaling_proof(tmp_path: Path) -> None:
    """Prove PK NCA computes real linear-log trapezoidal AUC and half-life from concentration-time arrays."""
    ws = tmp_path / "ws-pk-diff"
    ws.mkdir(parents=True, exist_ok=True)

    # Exponential decay with exact half-life t_1/2 = 1.0 hour: C(t) = C0 * (0.5)^t
    study_1x = {
        "schema": "pkde.pk-study.v1",
        "study_id": "rat-iv-1x",
        "species": "rat",
        "route": "iv",
        "dose_mg_kg": 10.0,
        "time_units": "h",
        "concentration_units": "ng/mL",
        "time_points": [0.0, 1.0, 2.0, 3.0, 4.0],
        "concentrations": [1000.0, 500.0, 250.0, 125.0, 62.5],
    }
    study_2x = {
        **study_1x,
        "study_id": "rat-iv-2x",
        "concentrations": [2000.0, 1000.0, 500.0, 250.0, 125.0],
    }

    p1_file = tmp_path / "study_1x.json"
    p2_file = tmp_path / "study_2x.json"
    p1_file.write_text(json.dumps(study_1x), encoding="utf-8")
    p2_file.write_text(json.dumps(study_2x), encoding="utf-8")

    for sfile, sid in ((p1_file, "rat-iv-1x"), (p2_file, "rat-iv-2x")):
        r_ing = pkde_exec(
            f"pk ingest {sfile} --json",
            project_dir=str(ws),
            auto_refresh_dashboard=False,
        )
        assert r_ing["ok"] is True, r_ing
        r_nca = pkde_exec(
            f"pk nca raw/pk/{sid}.pk-study.json --json",
            project_dir=str(ws),
            auto_refresh_dashboard=False,
        )
        assert r_nca["ok"] is True, r_nca
        r_ana = pkde_exec(
            f"pk analyze raw/pk/{sid}.pk-nca.json --json",
            project_dir=str(ws),
            auto_refresh_dashboard=False,
        )
        assert r_ana["ok"] is True, r_ana

    nca_1x = json.loads(
        (ws / "raw/pk/rat-iv-1x.pk-nca.json").read_text(encoding="utf-8")
    )["parameters"]
    nca_2x = json.loads(
        (ws / "raw/pk/rat-iv-2x.pk-nca.json").read_text(encoding="utf-8")
    )["parameters"]

    # Doubling concentration at every timepoint must exactly double Cmax, AUC_0_t, and AUC_0_inf
    assert math.isclose(nca_1x["cmax"], 1000.0, rel_tol=1e-6)
    assert math.isclose(nca_2x["cmax"], 2000.0, rel_tol=1e-6)
    assert math.isclose(nca_2x["auc_0_t"], 2.0 * nca_1x["auc_0_t"], rel_tol=1e-5)
    assert math.isclose(nca_2x["auc_0_inf"], 2.0 * nca_1x["auc_0_inf"], rel_tol=1e-5)

    # Terminal half-life for C(t) = C0 * 2^(-t) must be exactly 1.0 hour (lambda_z = ln(2)) for both
    assert math.isclose(nca_1x["half_life"], 1.0, rel_tol=1e-3)
    assert math.isclose(nca_2x["half_life"], 1.0, rel_tol=1e-3)
    assert math.isclose(nca_1x["lambda_z"], math.log(2.0), rel_tol=1e-3)


def test_pocket_geometric_positive_vs_negative_control(tmp_path: Path) -> None:
    """Prove geometric pocket detector finds cavities in 3D shells and returns 0 pockets on a 1D linear chain."""
    ws = tmp_path / "ws-pocket-controls"
    struct_dir = ws / "raw" / "structures"
    struct_dir.mkdir(parents=True, exist_ok=True)

    # Positive control: enclosed 3D spherical receptor
    pos_pdb = struct_dir / "POS_SHELL.pdb"
    _write_synthetic_cavity_pdb(pos_pdb)

    # Negative control: 1D linear chain of atoms along the X axis (cannot enclose any 3D cavity)
    neg_pdb = struct_dir / "NEG_LINEAR.pdb"
    linear_lines = ["HEADER    LINEAR CHAIN", "EXPDTA    X-RAY DIFFRACTION"]
    for serial in range(1, 25):
        x, y, z = serial * 3.8, 0.0, 0.0
        linear_lines.append(
            f"ATOM  {serial:5d}  CA  ALA A{serial:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00           C  "
        )
    linear_lines.append("END")
    neg_pdb.write_text("\n".join(linear_lines) + "\n", encoding="utf-8")

    res_pos = pkde_exec(
        f"pocket run {pos_pdb} --backend geometric --json",
        project_dir=str(ws),
        auto_refresh_dashboard=False,
    )
    assert res_pos["ok"] is True, res_pos
    assert res_pos["data"]["n_pockets"] >= 1

    res_neg = pkde_exec(
        f"pocket run {neg_pdb} --backend geometric --json",
        project_dir=str(ws),
        auto_refresh_dashboard=False,
    )
    assert res_neg["ok"] is True, res_neg
    assert res_neg["data"]["n_pockets"] == 0


def test_native_hypex_elo_prox_end_to_end_execution(tmp_path: Path) -> None:
    """Prove bin/hypex, bin/elo, and bin/prox execute real tournament datastore, Elo rating, and TF-IDF clustering."""
    hypex_bin = str(REPO_ROOT / "bin" / "hypex")
    elo_bin = str(REPO_ROOT / "bin" / "elo")
    prox_bin = str(REPO_ROOT / "bin" / "prox")
    schema_dir = str(
        REPO_ROOT / "tools" / "vendor" / "hypex" / "hypothesis-explorer" / "schemas"
    )

    def _run_tournament(run_name: str, winner_id: str) -> dict:
        base_dir = tmp_path / run_name
        base_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                hypex_bin,
                "--run-dir",
                str(base_dir),
                "--schema-dir",
                schema_dir,
                "init-run",
                "run-01",
                "--goal",
                "Identify selective KRAS G12D allosteric pockets",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        run_path = base_dir / "run-01"

        hyps = [
            {
                "title": "Switch-II salt-bridge allosteric lock",
                "statement": "Targeting Asp12 and Gln61 in the GDP-bound state stabilizes Switch-II.",
                "mechanism": "Non-covalent salt bridge with Asp12 blocks SOS1-mediated nucleotide exchange.",
                "predictions": [" >100x selectivity over WT KRAS in nucleotide exchange assay"],
                "experiments": [
                    {
                        "design": "TR-FRET GDP/GTP exchange assay on KRAS G12D vs WT",
                        "readout": "IC50 ratio WT/G12D",
                        "est_difficulty": "low",
                    }
                ],
                "evidence": [
                    {
                        "lit_id": "PMID:35672450",
                        "role": "supports",
                        "note": "Demonstrated Switch-II pocket plasticity.",
                    }
                ],
                "focus_area": "structural-allostery",
                "lineage": {"parents": [], "operator": "null"},
                "status": "active",
                "created_by": "hypex-generation",
                "epoch": 0,
                "created_at": "2026-10-16T12:00:00Z",
            },
            {
                "title": "PROTAC ternary complex degradation via VHL recruitment",
                "statement": "Recruiting VHL E3 ligase to KRAS G12D induces selective proteasomal degradation.",
                "mechanism": "Bifunctional linker bridges Switch-II ligand and VHL hydroxyproline mimetic.",
                "predictions": ["DC50 < 50 nM in AsPC-1 cells within 6 hours"],
                "experiments": [
                    {
                        "design": "HiBiT-KRAS G12D cellular degradation time-course",
                        "readout": "DC50 and Dmax at 6h",
                        "est_difficulty": "med",
                    }
                ],
                "evidence": [
                    {
                        "lit_id": "PMID:37123456",
                        "role": "supports",
                        "note": "VHL-based degraders spare wild-type RAS.",
                    }
                ],
                "focus_area": "targeted-protein-degradation",
                "lineage": {"parents": [], "operator": "null"},
                "status": "active",
                "created_by": "hypex-generation",
                "epoch": 0,
                "created_at": "2026-10-16T12:01:00Z",
            },
            {
                "title": "Switch-II Asp12 hydrogen-bond network stabilization",
                "statement": "Locking Asp12 and Gln61 in GDP-bound KRAS G12D prevents SOS1 catalysis.",
                "mechanism": "Direct salt bridge to Asp12 sidechain carboxyl in Switch-II pocket.",
                "predictions": ["High affinity KD < 1 nM by SPR against GDP-KRAS G12D"],
                "experiments": [
                    {
                        "design": "Biacore SPR binding kinetics on biotinylated KRAS G12D",
                        "readout": "KD and k_off",
                        "est_difficulty": "low",
                    }
                ],
                "evidence": [
                    {
                        "lit_id": "PMID:35672450",
                        "role": "supports",
                        "note": "Crystal structure of MRTX1133 in Switch-II pocket.",
                    }
                ],
                "focus_area": "structural-allostery",
                "lineage": {"parents": [], "operator": "null"},
                "status": "active",
                "created_by": "hypex-generation",
                "epoch": 0,
                "created_at": "2026-10-16T12:02:00Z",
            },
        ]

        for h in hyps:
            subprocess.run(
                [
                    hypex_bin,
                    "--run-dir",
                    str(base_dir),
                    "--schema-dir",
                    schema_dir,
                    "--run",
                    "run-01",
                    "add-hypothesis",
                    "-",
                ],
                input=json.dumps(h),
                check=True,
                capture_output=True,
                text=True,
            )

        match_rec = {
            "epoch": 0,
            "a": "H-0001",
            "b": "H-0002",
            "format": "single-turn",
            "winner": winner_id,
            "margin": "decisive",
            "criterion_scores": {
                "novelty": {"a": 4, "b": 4},
                "plausibility": {"a": 5 if winner_id == "H-0001" else 2, "b": 2 if winner_id == "H-0001" else 5},
                "testability": {"a": 5 if winner_id == "H-0001" else 3, "b": 3 if winner_id == "H-0001" else 5},
            },
            "rationale": f"{winner_id} has stronger direct biophysical tractability.",
            "judge": "hypex-tournament",
            "created_at": "2026-10-16T12:05:00Z",
        }
        subprocess.run(
            [
                hypex_bin,
                "--run-dir",
                str(base_dir),
                "--schema-dir",
                schema_dir,
                "--run",
                "run-01",
                "add-match",
                "-",
            ],
            input=json.dumps(match_rec),
            check=True,
            capture_output=True,
            text=True,
        )

        # Compute Elo ratings from the match ledger
        subprocess.run(
            [elo_bin, "--run-dir", str(run_path), "recompute"],
            check=True,
            capture_output=True,
            text=True,
        )

        # Run prox TF-IDF embedding, similarity graph, and clustering
        subprocess.run(
            [prox_bin, "embed", "--run-dir", str(run_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [prox_bin, "graph", "--run-dir", str(run_path), "--threshold", "0.1"],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [prox_bin, "clusters", "--run-dir", str(run_path)],
            check=True,
            capture_output=True,
            text=True,
        )

        ratings_doc = json.loads(
            (run_path / "ratings" / "epoch-0.json").read_text(encoding="utf-8")
        )
        graph_doc = json.loads(
            (run_path / "proximity" / "graph.json").read_text(encoding="utf-8")
        )
        return {"ratings": ratings_doc, "graph": graph_doc}

    # Tournament A: H-0001 beats H-0002
    res_a = _run_tournament("tourn-a", "H-0001")
    elo_a = res_a["ratings"]["ratings"]
    assert elo_a["H-0001"]["elo"] == 1520
    assert elo_a["H-0002"]["elo"] == 1480

    # Tournament B: H-0002 beats H-0001 (flipped outcome -> flipped Elo ratings!)
    res_b = _run_tournament("tourn-b", "H-0002")
    elo_b = res_b["ratings"]["ratings"]
    assert elo_b["H-0002"]["elo"] == 1520
    assert elo_b["H-0001"]["elo"] == 1480

    # Verify TF-IDF cosine similarity between the two Switch-II hypotheses (H-0001 & H-0003)
    # is higher than between PROTAC (H-0002) and Switch-II (H-0003)
    nodes = res_a["graph"]["nodes"]
    sim_1_3 = next(
        (e["similarity"] for e in nodes["H-0001"]["edges"] if e["target"] == "H-0003"),
        0.0,
    )
    sim_2_3 = next(
        (e["similarity"] for e in nodes["H-0002"]["edges"] if e["target"] == "H-0003"),
        0.0,
    )
    assert sim_1_3 > 0.4
    assert sim_1_3 > sim_2_3 * 3.0


def test_validator_sha256_tamper_detection_proof(tmp_path: Path) -> None:
    """Prove that modifying 1 byte of a Layer 0 JSON file after stamping causes pkde validate check to fail."""
    from pkde.core.env import CLI_VERSION
    from pkde.core.provenance import sha256_file

    ws = tmp_path / "ws-tamper"
    dispatch = pkde_dispatch_workorder(
        {
            "decision_question": "Verify SHA-256 tamper detection on Layer 0 artifact.",
            "requested_role": "computational-biologist",
            "deliverables": {
                "layer_0_classes": ["pkde.genetics"],
                "layer_1": ["findings/computational-biology/tamper-test.md"],
            },
        },
        project_dir=str(ws),
    )
    wo_id = dispatch["work_order_id"]
    run_id = dispatch["run_id"]

    raw_file = ws / "raw/genomics/EGFR.gnomad-constraint.json"
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    raw_file.write_text(
        json.dumps({"gene": "EGFR", "constraint": {"pLI": 0.99}}, indent=2) + "\n",
        encoding="utf-8",
    )
    original_sha = sha256_file(raw_file)

    (ws / "raw/genomics/EGFR.gnomad-constraint.json.meta.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "record_type": "provenance",
                "command": "pkde genetics fetch EGFR --json",
                "cli_version": CLI_VERSION,
                "work_order_id": wo_id,
                "outputs": [
                    {
                        "path": "raw/genomics/EGFR.gnomad-constraint.json",
                        "sha256": original_sha,
                    }
                ],
                "mandatory_relays": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (ws / "raw/genomics/EGFR.gnomad-constraint.json.analysis.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "record_type": "analysis",
                "source": "raw/genomics/EGFR.gnomad-constraint.json",
                "threshold_set": "genetics-v1",
                "work_order_id": wo_id,
                "verdict": "pass",
                "summary": "EGFR pLI is 0.99.",
                "mandatory_relays": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    finding_file = ws / "findings/computational-biology/tamper-test.md"
    finding_file.parent.mkdir(parents=True, exist_ok=True)
    finding_file.write_text(
        f"# EGFR Genetics ({wo_id}-r1)\n\n"
        "## Summary\n"
        "EGFR has pLI of 0.99 {source: raw/genomics/EGFR.gnomad-constraint.json $.constraint.pLI}.\n\n"
        "## Verdict\nPASS\n\n"
        "## Evidence\n- [EGFR JSON](../../raw/genomics/EGFR.gnomad-constraint.json)\n",
        encoding="utf-8",
    )

    # 1. Untampered artifact passes all 10 checks
    gate_pass = pkde_validate_and_gate(wo_id, run_id, project_dir=str(ws))
    assert gate_pass["ok"] is True
    assert gate_pass["status"] == "PASSED"

    # 2. Tamper with 1 byte in the Layer 0 JSON file (0.99 -> 0.98) without updating .meta.json
    raw_file.write_text(
        json.dumps({"gene": "EGFR", "constraint": {"pLI": 0.98}}, indent=2) + "\n",
        encoding="utf-8",
    )
    val_tampered = pkde_exec(
        f"validate check {wo_id} --dry-run --json",
        project_dir=str(ws),
        auto_refresh_dashboard=False,
    )
    assert val_tampered["ok"] is False
    tampered_data = val_tampered["data"]
    assert tampered_data["result"] == "fail"
    failed_checks = {
        c["name"]: c for c in tampered_data["checks"] if c["result"] == "fail"
    }
    assert "unrecognized_json" in failed_checks
    assert (
        failed_checks["unrecognized_json"]["kind"] == "unrecognized_record_type"
    )
    assert "source_tags_resolve" in failed_checks
    assert failed_checks["source_tags_resolve"]["kind"] == "DATA_INTEGRITY"
