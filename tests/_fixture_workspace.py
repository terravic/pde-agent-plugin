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

"""Generate a complete Stage 1–3 KRAS G12D Demo Program Workspace & Interactive Scientific Dashboard.

Creates real Work Orders, Runs, Resource Leases, Correction Loops, 10-Check
Mechanical Validations, Layer 0 Scientific Artifacts (all 14 viewer types with
cryptographic .meta.json and .analysis.json sidecars), Layer 1 Findings,
Layer 2 Program State, and builds `demo_dashboard.html`.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(REPO_ROOT), str(REPO_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pde.core.context import init_project  # noqa: E402
from pde.core.env import CLI_VERSION, env_version  # noqa: E402
from pde.core.provenance import sha256_file  # noqa: E402
from pde_plugin.tool_bridge import (  # noqa: E402
    pde_dispatch_workorder,
    pde_exec,
    pde_render_dashboard,
    pde_validate_and_gate,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_layer0_with_provenance(
    project_root: Path,
    rel_path: str,
    content: str | dict[str, Any],
    *,
    wo_id: str,
    command: str,
    threshold_set: str,
    verdict: str,
    summary: str,
    thresholds_applied: dict[str, Any],
    mandatory_relays: list[dict[str, str]],
    metrics: dict[str, Any] | None = None,
) -> Path:
    """Write a Layer 0 file along with its cryptographic .meta.json and .analysis.json sidecars."""
    file_path = project_root / rel_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, dict):
        file_path.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
    else:
        file_path.write_text(content, encoding="utf-8")

    digest = sha256_file(file_path)
    stem_dir = file_path.parent
    base_name = file_path.name
    current_env = env_version()

    meta_path = stem_dir / f"{base_name}.meta.json"
    meta_record = {
        "schema_version": "1.0",
        "record_type": "provenance",
        "command": command,
        "cli_version": CLI_VERSION,
        "env_version": current_env,
        "created_at": _utc_now(),
        "work_order_id": wo_id,
        "outputs": [
            {
                "path": rel_path,
                "sha256": digest,
                "bytes": file_path.stat().st_size,
            }
        ],
        "mandatory_relays": mandatory_relays,
    }
    meta_path.write_text(json.dumps(meta_record, indent=2) + "\n", encoding="utf-8")

    analysis_path = stem_dir / f"{base_name}.analysis.json"
    analysis_record = {
        "schema_version": "1.0",
        "record_type": "analysis",
        "source": rel_path,
        "env_version": current_env,
        "source_sha256": digest,
        "threshold_set": threshold_set,
        "work_order_id": wo_id,
        "analyzed_at": _utc_now(),
        "verdict": verdict,
        "summary": summary,
        "thresholds_applied": thresholds_applied,
        "metrics": metrics or {},
        "mandatory_relays": mandatory_relays,
    }
    analysis_path.write_text(
        json.dumps(analysis_record, indent=2) + "\n", encoding="utf-8"
    )
    return file_path


def populate_demo_workspace(workspace_dir: Path) -> dict[str, Any]:
    """Populate *workspace_dir* with a complete Stage 1-3 KRAS G12D discovery program."""
    if workspace_dir.exists():
        shutil.rmtree(workspace_dir)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    init_project(workspace_dir)

    # Configure .pde/program.yaml with initial user_prompt
    user_prompt = (
        "Run a multi-disciplinary Stage 2 Hit-to-Lead discovery campaign for a selective "
        "non-covalent KRAS G12D Switch-II pocket inhibitor (MRTX1133 series) in pancreatic "
        "ductal adenocarcinoma (PDAC): evaluate human genetics, 3D Switch-II pocket druggability "
        "and docking poses, medicinal chemistry SAR and ADMET/PK/tox margins, and bypass resistance hypotheses."
    )
    (workspace_dir / ".pde" / "program.yaml").write_text(
        "name: KRAS-G12D-Selective-Inhibitor\n"
        f"user_prompt: {json.dumps(user_prompt)}\n"
        "target: KRAS (G12D)\n"
        "uniprot_id: P01116\n"
        "indication: Pancreatic Ductal Adenocarcinoma (PDAC)\n"
        "stage: Stage 2 - Hit-to-Lead & Switch-II Optimization\n"
        "cycle: 2\n",
        encoding="utf-8",
    )
    from pde.core import controlstore as _cs

    _cs.append_event(
        workspace_dir,
        {
            "type": "prompt.received",
            "subject_id": "science-program-lead",
            "from_state": "idle",
            "to_state": "running",
            "actor": "user",
            "detail": {
                "prompt": user_prompt,
                "summary": f'User prompt received by Science Program Lead: "{user_prompt}"',
            },
        },
    )
    _cs.append_event(
        workspace_dir,
        {
            "type": "agent.message",
            "subject_id": "research-operations-controller",
            "actor": "science-program-lead",
            "detail": {
                "recipient": "research-operations-controller",
                "summary": "Chartered Stage 2 Cycle 2 KRAS G12D campaign (DEC-001); authorizing 5 parallel specialist work orders (WO-001 through WO-005).",
            },
        },
    )

    # ------------------------------------------------------------------
    # WO-001: Computational Biologist (Genetics & Tissue Expression)
    # ------------------------------------------------------------------
    wo1 = pde_dispatch_workorder(
        {
            "decision_question": "Evaluate KRAS human genetic constraint (gnomAD) and normal tissue expression (GTEx) for on-target toxicity risk.",
            "requested_role": "computational-biologist",
            "stage": 1,
            "cycle": 1,
            "deliverables": {
                "layer_0_classes": ["pde.genetics", "pde.gtex"],
                "layer_1": ["findings/computational-biology/kras-genetics-expression.md"],
            },
        },
        project_dir=str(workspace_dir),
    )
    wo1_id, run1_id = wo1["work_order_id"], wo1["run_id"]

    _write_layer0_with_provenance(
        workspace_dir,
        "raw/genomics/KRAS.gnomad-constraint.json",
        {
            "gene": "KRAS",
            "ensembl_id": "ENSG00000133703",
            "uniprot_id": "P01116",
            "constraint": {
                "pLI": 0.98,
                "oe_lof_upper": 0.24,
                "loeuf": 0.24,
                "mis_z": 3.42,
                "syn_z": 0.18,
            },
            "disease_associations": [
                {"disease": "Pancreatic adenocarcinoma", "overall_score": 0.94},
                {"disease": "Colorectal adenocarcinoma", "overall_score": 0.91},
                {"disease": "Non-small cell lung carcinoma", "overall_score": 0.89},
            ],
        },
        wo_id=wo1_id,
        command="pde genetics fetch KRAS --json",
        threshold_set="genetics-v1",
        verdict="go_with_caution",
        summary="KRAS is strongly constrained against loss-of-function (pLI=0.98, LOEUF=0.24); mutant-selective G12D targeting is mandatory to spare wild-type KRAS.",
        thresholds_applied={"pLI_essential_cutoff": 0.90, "loeuf_constrained": 0.35},
        mandatory_relays=[
            {
                "code": "ESSENTIAL_GENE_WT_SPARING_REQUIRED",
                "target_role": "medicinal-chemist",
                "detail": "KRAS pLI=0.98 and LOEUF=0.24 require >=50x G12D vs WT selectivity.",
            }
        ],
        metrics={"pLI": 0.98, "LOEUF": 0.24, "mis_z": 3.42},
    )

    _write_layer0_with_provenance(
        workspace_dir,
        "raw/gtex/KRAS.tissue.json",
        {
            "gene": "KRAS",
            "unit": "TPM",
            "max_tpm": 48.5,
            "tissues": [
                {"tissue": "Colon - Transverse", "median_tpm": 48.5, "essential_organ": True},
                {"tissue": "Esophagus - Mucosa", "median_tpm": 42.1, "essential_organ": False},
                {"tissue": "Lung", "median_tpm": 36.8, "essential_organ": True},
                {"tissue": "Pancreas", "median_tpm": 22.4, "essential_organ": True},
                {"tissue": "Heart - Left Ventricle", "median_tpm": 18.2, "essential_organ": True},
                {"tissue": "Liver", "median_tpm": 14.9, "essential_organ": True},
                {"tissue": "Kidney - Cortex", "median_tpm": 19.7, "essential_organ": True},
            ],
        },
        wo_id=wo1_id,
        command="pde gtex fetch KRAS --json",
        threshold_set="expression-v1",
        verdict="pass",
        summary="Broad baseline WT expression across GI tract and lung (max 48.5 TPM in Colon); confirms need for G12D salt-bridge selectivity.",
        thresholds_applied={"high_expression_tpm": 50.0},
        mandatory_relays=[
            {
                "code": "GI_MUCOSA_WT_EXPRESSION_MONITOR",
                "target_role": "preclinical-toxicologist",
                "detail": "Monitor GI mucosal proliferation in rodent tox due to colon TPM 48.5.",
            }
        ],
        metrics={"max_tpm": 48.5, "pancreas_tpm": 22.4},
    )

    (workspace_dir / "findings/computational-biology/kras-genetics-expression.md").write_text(
        f"# KRAS Genetic Constraint & Tissue Expression Assessment ({wo1_id}-r1)\n\n"
        "## Summary\n"
        f"Executed human genetic constraint and normal tissue transcriptomic profiling for `{wo1_id}-r1`. "
        "KRAS exhibits extreme loss-of-function intolerance in gnomAD with pLI of 0.98 "
        "{source: raw/genomics/KRAS.gnomad-constraint.json $.constraint.pLI} and LOEUF of 0.24 "
        "{source: raw/genomics/KRAS.gnomad-constraint.json $.constraint.loeuf}.\n\n"
        "## Key Findings\n"
        "- **Missense & LoF Constraint**: Missense Z-score is 3.42 "
        "{source: raw/genomics/KRAS.gnomad-constraint.json $.constraint.mis_z}, confirming strong purifying selection.\n"
        "- **Oncology Driver Evidence**: Pancreatic adenocarcinoma association score is 0.94 "
        "{source: raw/genomics/KRAS.gnomad-constraint.json $.disease_associations[0].overall_score}.\n"
        "- **Normal Tissue Expression (GTEx)**: Peak expression occurs in Colon - Transverse at 48.5 "
        "{source: raw/gtex/KRAS.tissue.json $.max_tpm} TPM and Pancreas at 22.4 "
        "{source: raw/gtex/KRAS.tissue.json $.tissues[3].median_tpm} TPM.\n"
        "- **Relay: `ESSENTIAL_GENE_WT_SPARING_REQUIRED`** — Medicinal chemistry and docking must enforce >=50x G12D over WT selectivity.\n"
        "- **Relay: `GI_MUCOSA_WT_EXPRESSION_MONITOR`** — Preclinical toxicology must monitor GI mucosa.\n\n"
        "## Verdict\n"
        "**GO WITH CAUTION** — Proceed with non-covalent Switch-II pocket inhibitors specifically engaging Asp12.\n\n"
        "## Evidence\n"
        "- [KRAS gnomAD Constraint](../../raw/genomics/KRAS.gnomad-constraint.json)\n"
        "- [KRAS GTEx Expression](../../raw/gtex/KRAS.tissue.json)\n\n"
        "## Implications\n"
        "Wild-type KRAS sparing is the primary design constraint for Stage 2 hit-to-lead.\n",
        encoding="utf-8",
    )
    pde_validate_and_gate(wo1_id, run1_id, project_dir=str(workspace_dir))
    pde_exec(f"workorder accept {wo1_id} --json", project_dir=str(workspace_dir), auto_refresh_dashboard=False)

    # ------------------------------------------------------------------
    # WO-002: Structural Biologist (AlphaFold 3 Structure, PAE & Pockets)
    # ------------------------------------------------------------------
    wo2 = pde_dispatch_workorder(
        {
            "decision_question": "Characterize KRAS G12D structure confidence (pLDDT/PAE) and Switch-II pocket (SII-P) druggability.",
            "requested_role": "structural-biologist",
            "stage": 1,
            "cycle": 1,
            "resource_class": "af3",
            "deliverables": {
                "layer_0_classes": ["pde.structures", "pde.pocket"],
                "layer_1": ["findings/structural-biology/kras-g12d-structure-pockets.md"],
            },
        },
        project_dir=str(workspace_dir),
    )
    wo2_id, run2_id = wo2["work_order_id"], wo2["run_id"]

    residues = list(range(1, 170))
    plddt_scores = [
        round(94.2 - (0.18 * abs(r - 62)) if 58 <= r <= 72 else 92.8 - (r % 7) * 0.6, 1)
        for r in residues
    ]
    _write_layer0_with_provenance(
        workspace_dir,
        "raw/structures/KRAS_G12D.afdb.json",
        {
            "target": "KRAS_G12D",
            "uniprot_id": "P01116",
            "mean_plddt": 91.4,
            "ptm": 0.91,
            "residue_numbers": residues,
            "plddt": plddt_scores,
            "switch_ii_mean_plddt": 88.6,
        },
        wo_id=wo2_id,
        command="pde alphafold fetch P01116 --json",
        threshold_set="structure-v1",
        verdict="pass",
        summary="High-confidence G-domain fold (mean pLDDT 91.4, pTM 0.91) with well-defined Switch-II pocket.",
        thresholds_applied={"min_mean_plddt": 70.0, "min_pocket_plddt": 75.0},
        mandatory_relays=[
            {
                "code": "SWITCH_II_CONFORMATIONAL_PLASTICITY",
                "target_role": "computational-chemist",
                "detail": "Switch-II loop (residues 58-72, mean pLDDT 88.6) requires induced-fit receptor ensemble.",
            }
        ],
        metrics={"mean_plddt": 91.4, "switch_ii_mean_plddt": 88.6},
    )

    # 20x20 downsampled PAE matrix for fast interactive heatmap rendering
    pae_matrix = [
        [round(1.2 + 0.15 * abs(i - j) + (2.1 if (5 <= i <= 8) != (5 <= j <= 8) else 0.0), 2) for j in range(20)]
        for i in range(20)
    ]
    _write_layer0_with_provenance(
        workspace_dir,
        "raw/structures/KRAS_G12D.pae.json",
        {
            "target": "KRAS_G12D",
            "max_pae": 31.75,
            "mean_pae": 3.18,
            "predicted_aligned_error": pae_matrix,
        },
        wo_id=wo2_id,
        command="pde alphafold pae P01116 --json",
        threshold_set="structure-v1",
        verdict="pass",
        summary="Low inter-residue PAE across the catalytic G-domain core (mean PAE 3.18 A).",
        thresholds_applied={"max_domain_pae": 8.0},
        mandatory_relays=[],
        metrics={"mean_pae": 3.18},
    )

    cif_content = (
        "data_KRAS_G12D\n"
        "#\n"
        "loop_\n"
        "_atom_site.group_PDB\n"
        "_atom_site.id\n"
        "_atom_site.type_symbol\n"
        "_atom_site.label_atom_id\n"
        "_atom_site.label_alt_id\n"
        "_atom_site.label_comp_id\n"
        "_atom_site.label_asym_id\n"
        "_atom_site.label_entity_id\n"
        "_atom_site.label_seq_id\n"
        "_atom_site.pdbx_PDB_ins_code\n"
        "_atom_site.Cartn_x\n"
        "_atom_site.Cartn_y\n"
        "_atom_site.Cartn_z\n"
        "_atom_site.occupancy\n"
        "_atom_site.B_iso_or_equiv\n"
        "_atom_site.auth_seq_id\n"
        "_atom_site.auth_comp_id\n"
        "_atom_site.auth_asym_id\n"
        "_atom_site.auth_atom_id\n"
        "_atom_site.pdbx_PDB_model_num\n"
        "ATOM 1 N N . GLY A 1 10 ? 9.420 15.810 7.120 1.00 94.20 10 GLY A N 1\n"
        "ATOM 2 C CA . GLY A 1 10 ? 10.310 16.640 7.910 1.00 94.20 10 GLY A CA 1\n"
        "ATOM 3 C C . GLY A 1 10 ? 11.120 17.420 7.010 1.00 94.10 10 GLY A C 1\n"
        "ATOM 4 O O . GLY A 1 10 ? 11.010 17.310 5.790 1.00 93.90 10 GLY A O 1\n"
        "ATOM 5 N N . ALA A 1 11 ? 11.890 18.210 7.640 1.00 93.80 11 ALA A N 1\n"
        "ATOM 6 C CA . ALA A 1 11 ? 12.140 17.920 9.020 1.00 93.80 11 ALA A CA 1\n"
        "ATOM 7 C C . ALA A 1 11 ? 12.680 19.010 9.810 1.00 93.60 11 ALA A C 1\n"
        "ATOM 8 O O . ALA A 1 11 ? 13.020 20.060 9.280 1.00 93.50 11 ALA A O 1\n"
        "ATOM 9 C CB . ALA A 1 11 ? 11.010 17.210 9.740 1.00 93.40 11 ALA A CB 1\n"
        "ATOM 10 N N . ASP A 1 12 ? 12.410 18.220 9.140 1.00 93.40 12 ASP A N 1\n"
        "ATOM 11 C CA . ASP A 1 12 ? 13.520 19.010 9.650 1.00 93.40 12 ASP A CA 1\n"
        "ATOM 12 C C . ASP A 1 12 ? 14.120 19.880 8.580 1.00 93.10 12 ASP A C 1\n"
        "ATOM 13 O O . ASP A 1 12 ? 13.610 20.940 8.220 1.00 92.90 12 ASP A O 1\n"
        "ATOM 14 C CB . ASP A 1 12 ? 14.810 18.240 9.910 1.00 92.80 12 ASP A CB 1\n"
        "ATOM 15 C CG . ASP A 1 12 ? 15.940 19.120 10.420 1.00 92.10 12 ASP A CG 1\n"
        "ATOM 16 O OD1 . ASP A 1 12 ? 15.780 20.340 10.580 1.00 91.50 12 ASP A OD1 1\n"
        "ATOM 17 O OD2 . ASP A 1 12 ? 17.020 18.560 10.680 1.00 91.80 12 ASP A OD2 1\n"
        "ATOM 18 N N . GLY A 1 13 ? 15.220 19.440 8.010 1.00 92.70 13 GLY A N 1\n"
        "ATOM 19 C CA . GLY A 1 13 ? 15.980 20.180 7.020 1.00 92.60 13 GLY A CA 1\n"
        "ATOM 20 C C . GLY A 1 13 ? 17.120 19.380 6.440 1.00 92.40 13 GLY A C 1\n"
        "ATOM 21 O O . GLY A 1 13 ? 17.340 18.210 6.760 1.00 92.20 13 GLY A O 1\n"
        "ATOM 22 N N . VAL A 1 14 ? 17.880 20.020 5.560 1.00 92.50 14 VAL A N 1\n"
        "ATOM 23 C CA . VAL A 1 14 ? 19.010 19.410 4.920 1.00 92.50 14 VAL A CA 1\n"
        "ATOM 24 C C . VAL A 1 14 ? 19.940 18.820 5.960 1.00 92.30 14 VAL A C 1\n"
        "ATOM 25 O O . VAL A 1 14 ? 20.420 17.710 5.780 1.00 92.10 14 VAL A O 1\n"
        "ATOM 26 N N . GLY A 1 15 ? 20.180 19.560 7.040 1.00 92.00 15 GLY A N 1\n"
        "ATOM 27 C CA . GLY A 1 15 ? 21.020 19.120 8.120 1.00 92.00 15 GLY A CA 1\n"
        "ATOM 28 C C . GLY A 1 15 ? 20.380 18.040 8.960 1.00 91.90 15 GLY A C 1\n"
        "ATOM 29 O O . GLY A 1 15 ? 20.980 17.020 9.280 1.00 91.80 15 GLY A O 1\n"
        "ATOM 30 N N . LYS A 1 16 ? 19.120 18.260 9.320 1.00 92.40 16 LYS A N 1\n"
        "ATOM 31 C CA . LYS A 1 16 ? 18.380 17.310 10.120 1.00 92.40 16 LYS A CA 1\n"
        "ATOM 32 C C . LYS A 1 16 ? 18.840 15.880 9.920 1.00 92.20 16 LYS A C 1\n"
        "ATOM 33 O O . LYS A 1 16 ? 19.010 15.140 10.880 1.00 92.00 16 LYS A O 1\n"
        "ATOM 34 N N . ALA A 1 59 ? 17.240 20.210 11.420 1.00 88.90 59 ALA A N 1\n"
        "ATOM 35 C CA . ALA A 1 59 ? 17.680 20.840 12.640 1.00 88.90 59 ALA A CA 1\n"
        "ATOM 36 C C . ALA A 1 59 ? 18.120 22.240 12.320 1.00 88.60 59 ALA A C 1\n"
        "ATOM 37 O O . ALA A 1 59 ? 18.020 23.120 13.160 1.00 88.50 59 ALA A O 1\n"
        "ATOM 38 N N . GLY A 1 60 ? 18.610 22.410 11.110 1.00 88.40 60 GLY A N 1\n"
        "ATOM 39 C CA . GLY A 1 60 ? 18.450 21.120 12.340 1.00 88.40 60 GLY A CA 1\n"
        "ATOM 40 C C . GLY A 1 60 ? 19.320 21.480 13.510 1.00 88.10 60 GLY A C 1\n"
        "ATOM 41 O O . GLY A 1 60 ? 19.610 20.620 14.340 1.00 88.00 60 GLY A O 1\n"
        "ATOM 42 N N . GLN A 1 61 ? 19.720 22.740 13.580 1.00 87.90 61 GLN A N 1\n"
        "ATOM 43 C CA . GLN A 1 61 ? 19.820 22.410 14.110 1.00 87.90 61 GLN A CA 1\n"
        "ATOM 44 C C . GLN A 1 61 ? 20.880 21.420 14.540 1.00 87.50 61 GLN A C 1\n"
        "ATOM 45 O O . GLN A 1 61 ? 21.620 21.740 15.460 1.00 87.20 61 GLN A O 1\n"
        "ATOM 46 N N . GLU A 1 62 ? 20.940 20.240 13.940 1.00 86.20 62 GLU A N 1\n"
        "ATOM 47 C CA . GLU A 1 62 ? 21.140 20.980 15.620 1.00 86.20 62 GLU A CA 1\n"
        "ATOM 48 C C . GLU A 1 62 ? 22.120 19.940 15.140 1.00 86.80 62 GLU A C 1\n"
        "ATOM 49 O O . GLU A 1 62 ? 22.980 19.520 15.900 1.00 86.90 62 GLU A O 1\n"
        "ATOM 50 N N . GLU A 1 63 ? 21.980 19.540 13.880 1.00 87.80 63 GLU A N 1\n"
        "ATOM 51 C CA . GLU A 1 63 ? 22.420 18.420 13.120 1.00 87.80 63 GLU A CA 1\n"
        "ATOM 52 C C . GLU A 1 63 ? 22.580 18.840 11.680 1.00 88.20 63 GLU A C 1\n"
        "ATOM 53 O O . GLU A 1 63 ? 23.420 18.320 10.960 1.00 88.40 63 GLU A O 1\n"
        "ATOM 54 N N . TYR A 1 64 ? 21.780 19.820 11.280 1.00 89.10 64 TYR A N 1\n"
        "ATOM 55 C CA . TYR A 1 64 ? 22.610 19.450 13.880 1.00 89.10 64 TYR A CA 1\n"
        "ATOM 56 C C . TYR A 1 64 ? 21.480 18.620 13.280 1.00 89.50 64 TYR A C 1\n"
        "ATOM 57 O O . TYR A 1 64 ? 21.680 17.440 13.020 1.00 89.70 64 TYR A O 1\n"
        "ATOM 58 N N . ARG A 1 68 ? 20.420 17.640 11.580 1.00 91.20 68 ARG A N 1\n"
        "ATOM 59 C CA . ARG A 1 68 ? 19.950 16.820 12.450 1.00 91.20 68 ARG A CA 1\n"
        "ATOM 60 C C . ARG A 1 68 ? 18.620 16.240 12.020 1.00 91.50 68 ARG A C 1\n"
        "ATOM 61 O O . ARG A 1 68 ? 18.420 15.040 12.140 1.00 91.60 68 ARG A O 1\n"
        "ATOM 62 N N . HIS A 1 95 ? 16.820 14.840 10.320 1.00 94.10 95 HIS A N 1\n"
        "ATOM 63 C CA . HIS A 1 95 ? 16.120 15.440 11.210 1.00 94.10 95 HIS A CA 1\n"
        "ATOM 64 C C . HIS A 1 95 ? 15.840 16.820 11.740 1.00 94.30 95 HIS A C 1\n"
        "ATOM 65 O O . HIS A 1 95 ? 15.120 17.580 11.120 1.00 94.40 95 HIS A O 1\n"
        "ATOM 66 N N . TYR A 1 96 ? 16.420 17.140 12.880 1.00 94.60 96 TYR A N 1\n"
        "ATOM 67 C CA . TYR A 1 96 ? 15.280 16.890 13.640 1.00 94.60 96 TYR A CA 1\n"
        "ATOM 68 C C . TYR A 1 96 ? 14.620 15.620 13.140 1.00 94.20 96 TYR A C 1\n"
        "ATOM 69 O O . TYR A 1 96 ? 13.840 15.020 13.860 1.00 94.00 96 TYR A O 1\n"
        "ATOM 70 N N . GLN A 1 99 ? 14.920 15.220 11.940 1.00 93.80 99 GLN A N 1\n"
        "ATOM 71 C CA . GLN A 1 99 ? 14.110 14.620 13.950 1.00 93.80 99 GLN A CA 1\n"
        "ATOM 72 C C . GLN A 1 99 ? 13.120 13.740 13.220 1.00 93.60 99 GLN A C 1\n"
        "ATOM 73 O O . GLN A 1 99 ? 12.340 13.060 13.880 1.00 93.50 99 GLN A O 1\n"
        "#\n"
    )
    _write_layer0_with_provenance(
        workspace_dir,
        "raw/structures/KRAS_G12D.cif",
        cif_content,
        wo_id=wo2_id,
        command="pde structure fetch 7RPZ --format cif --json",
        threshold_set="structure-v1",
        verdict="pass",
        summary="High-resolution Switch-II pocket receptor coordinates prepared for Asp12 salt-bridge docking.",
        thresholds_applied={"max_resolution": 2.5},
        mandatory_relays=[],
    )

    _write_layer0_with_provenance(
        workspace_dir,
        "raw/pocket/KRAS_G12D_SIIP.pockets.json",
        {
            "structure": "raw/structures/KRAS_G12D.cif",
            "top_druggability_score": 0.84,
            "pockets": [
                {
                    "pocket_id": "POCKET_1_SIIP",
                    "name": "Switch-II Allosteric Pocket (SII-P)",
                    "druggability_score": 0.84,
                    "volume_a3": 542.6,
                    "hydrophobicity_score": 38.4,
                    "polar_sasa": 164.2,
                    "key_residues": ["ASP12", "GLY60", "GLN61", "GLU62", "ARG68", "HIS95", "TYR96", "GLN99"],
                },
                {
                    "pocket_id": "POCKET_2_GNBP",
                    "name": "GDP/GTP Nucleotide Site",
                    "druggability_score": 0.41,
                    "volume_a3": 388.0,
                    "hydrophobicity_score": 12.1,
                    "polar_sasa": 248.5,
                    "key_residues": ["GLY13", "VAL14", "GLY15", "LYS16", "SER17"],
                },
            ],
        },
        wo_id=wo2_id,
        command="pde pocket detect raw/structures/KRAS_G12D.cif --json",
        threshold_set="pocket-v1",
        verdict="pass",
        summary="Switch-II allosteric pocket (POCKET_1_SIIP) is highly druggable (score 0.84, volume 542.6 A^3) with direct access to Asp12 carboxylate.",
        thresholds_applied={"min_druggability_score": 0.60, "min_volume_a3": 300.0},
        mandatory_relays=[
            {
                "code": "ASP12_SALT_BRIDGE_ANCHOR_REQUIRED",
                "target_role": "medicinal-chemist",
                "detail": "POCKET_1_SIIP druggability=0.84 relies on basic bicyclic amine engaging Asp12 OD1/OD2 plus His95/Tyr96 groove.",
            }
        ],
        metrics={"top_druggability_score": 0.84, "siip_volume_a3": 542.6},
    )

    (workspace_dir / "findings/structural-biology/kras-g12d-structure-pockets.md").write_text(
        f"# KRAS G12D Structure Confidence & Switch-II Pocket Druggability ({wo2_id}-r1)\n\n"
        "## Summary\n"
        f"Completed structural confidence and pocket druggability evaluation for `{wo2_id}-r1`. "
        "The KRAS G12D catalytic domain shows mean pLDDT of 91.4 "
        "{source: raw/structures/KRAS_G12D.afdb.json $.mean_plddt} and mean PAE of 3.18 "
        "{source: raw/structures/KRAS_G12D.pae.json $.mean_pae} A.\n\n"
        "## Key Findings\n"
        "- **Switch-II Loop Plasticity**: Switch-II residues 58-72 exhibit mean pLDDT of 88.6 "
        "{source: raw/structures/KRAS_G12D.afdb.json $.switch_ii_mean_plddt}.\n"
        "- **Switch-II Allosteric Pocket (SII-P)**: `POCKET_1_SIIP` achieves a druggability score of 0.84 "
        "{source: raw/pocket/KRAS_G12D_SIIP.pockets.json $.top_druggability_score} with volume 542.6 "
        "{source: raw/pocket/KRAS_G12D_SIIP.pockets.json $.pockets[0].volume_a3} A^3.\n"
        "- **Relay: `SWITCH_II_CONFORMATIONAL_PLASTICITY`** — Use ensemble docking across Switch-II loop states.\n"
        "- **Relay: `ASP12_SALT_BRIDGE_ANCHOR_REQUIRED`** — Anchor basic amine against Asp12 carboxylate.\n\n"
        "## Verdict\n"
        "**PASS** — Switch-II pocket is structurally validated for non-covalent salt-bridge inhibitor design.\n\n"
        "## Evidence\n"
        "- [KRAS G12D pLDDT Profile](../../raw/structures/KRAS_G12D.afdb.json)\n"
        "- [KRAS G12D PAE Matrix](../../raw/structures/KRAS_G12D.pae.json)\n"
        "- [Switch-II Pocket Druggability](../../raw/pocket/KRAS_G12D_SIIP.pockets.json)\n\n"
        "## Implications\n"
        "Prioritize pyrido[4,3-d]pyrimidine scaffolds projecting a (1R,5S)-3,8-diazabicyclo[3.2.1]octane warhead toward Asp12.\n",
        encoding="utf-8",
    )
    pde_validate_and_gate(wo2_id, run2_id, project_dir=str(workspace_dir))
    pde_exec(f"workorder accept {wo2_id} --json", project_dir=str(workspace_dir), auto_refresh_dashboard=False)

    # ------------------------------------------------------------------
    # WO-003: Medicinal Chemist & ADMET (Compound SDF, BRICS SAR, ADMET Radar)
    # Includes an authentic 1-cycle mechanical correction loop demonstration!
    # ------------------------------------------------------------------
    wo3 = pde_dispatch_workorder(
        {
            "decision_question": "Profile lead series MRTX1133 3D conformer, BRICS fragment SAR, and 5-axis ADMET properties.",
            "requested_role": "medicinal-chemist",
            "stage": 2,
            "cycle": 1,
            "deliverables": {
                "layer_0_classes": ["pde.compounds", "pde.sar", "pde.admet"],
                "layer_1": ["findings/medicinal-chemistry/mrtx1133-sar-admet.md"],
            },
        },
        project_dir=str(workspace_dir),
    )
    wo3_id, run3_id = wo3["work_order_id"], wo3["run_id"]

    sdf_content = (
        "MRTX1133\n"
        "  RDKit          3D\n\n"
        " 10  9  0  0  0  0  0  0  0  0999 V2000\n"
        "   15.1200   19.4500   10.8200 N   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "   16.3400   18.8900   11.2100 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "   17.4500   19.6200   11.8800 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "   17.3100   20.9800   12.1400 N   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "   16.1100   21.5400   11.7500 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "   14.9800   20.8100   11.0900 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "   18.6800   18.9500   12.3100 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "   19.8200   19.6100   12.8900 F   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "   16.4800   17.5100   10.9500 O   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "   15.9200   22.8900   12.0200 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "  1  2  1  0\n"
        "  2  3  2  0\n"
        "  3  4  1  0\n"
        "  4  5  2  0\n"
        "  5  6  1  0\n"
        "  6  1  2  0\n"
        "  3  7  1  0\n"
        "  7  8  1  0\n"
        "  2  9  1  0\n"
        "M  END\n$$$$\n"
    )
    _write_layer0_with_provenance(
        workspace_dir,
        "raw/compounds/MRTX1133.3d.sdf",
        sdf_content,
        wo_id=wo3_id,
        command="pde compound conformer MRTX1133 --json",
        threshold_set="compound-v1",
        verdict="pass",
        summary="Low-energy 3D conformer generated for MRTX1133 with protonated diazabicyclooctane amine.",
        thresholds_applied={"max_strain_energy_kcal": 5.0},
        mandatory_relays=[],
    )

    _write_layer0_with_provenance(
        workspace_dir,
        "raw/sar/MRTX1133_series.brics.json",
        {
            "series_name": "Pyridopyrimidine Switch-II Series",
            "parent_compound": "MRTX1133",
            "n_fragments": 4,
            "fragments": [
                {
                    "fragment_id": "FRAG-01",
                    "smiles": "[1*]N1CC2CCC1CN2",
                    "role": "Asp12 Salt-Bridge Warhead",
                    "kd_contribution_kcal": -4.8,
                    "frequency": 0.95,
                },
                {
                    "fragment_id": "FRAG-02",
                    "smiles": "[3*]c1nc2cnc(F)cc2c([4*])n1",
                    "role": "8-Fluoropyrido[4,3-d]pyrimidine Core",
                    "kd_contribution_kcal": -3.6,
                    "frequency": 1.00,
                },
                {
                    "fragment_id": "FRAG-03",
                    "smiles": "[8*]c1cccc2cccc(O)c12",
                    "role": "3-Hydroxynaphthyl His95/Tyr96 Clamp",
                    "kd_contribution_kcal": -3.2,
                    "frequency": 0.88,
                },
                {
                    "fragment_id": "FRAG-04",
                    "smiles": "[14*]OCC12CCCN1CC2=CF",
                    "role": "Fluorinated Pyrrolizidine Solvent Tail",
                    "kd_contribution_kcal": -1.5,
                    "frequency": 0.72,
                },
            ],
        },
        wo_id=wo3_id,
        command="pde mmp brics MRTX1133 --json",
        threshold_set="sar-v1",
        verdict="pass",
        summary="BRICS decomposition identifies 4 pharmacophoric synthons; FRAG-01 diazabicyclooctane provides -4.8 kcal/mol Asp12 anchor.",
        thresholds_applied={"min_fragments": 2},
        mandatory_relays=[],
        metrics={"n_fragments": 4, "warhead_dg": -4.8},
    )

    _write_layer0_with_provenance(
        workspace_dir,
        "raw/admet/MRTX1133.predict.json",
        {
            "compound_id": "MRTX1133",
            "mw": 600.6,
            "clogp": 4.12,
            "tpsa": 93.5,
            "hbd": 2,
            "hba": 8,
            "mpo_score": 0.74,
            "radar_axes": {
                "Metabolic Stability": 0.82,
                "CYP Inhibition": 0.88,
                "Permeability": 0.46,
                "hERG Liability": 0.79,
                "Solubility": 0.76,
            },
            "predictions": {
                "caco2_papp_1e6": 2.4,
                "hlm_t12_min": 68.0,
                "cyp3a4_ic50_um": 18.5,
                "herg_ic50_um": 14.2,
                "kinetic_solubility_um": 85.0,
                "oral_bioavailability_pct": 11.5,
            },
        },
        wo_id=wo3_id,
        command="pde admet predict MRTX1133 --json",
        threshold_set="admet-v1",
        verdict="pass_with_warnings",
        summary="Favorable metabolic stability (HLM t1/2=68 min) and hERG margin (IC50=14.2 uM), but moderate permeability (Papp=2.4e-6 cm/s, F%=11.5%).",
        thresholds_applied={"min_papp": 5.0, "min_herg_ic50_um": 10.0},
        mandatory_relays=[
            {
                "code": "LOW_ORAL_PERMEABILITY_PRODRUG_EVAL",
                "target_role": "admet-dmpk-scientist",
                "detail": "Caco-2 Papp=2.4e-6 cm/s and F%=11.5% require phenolic ester prodrug or IV/SC formulation strategy.",
            }
        ],
        metrics={"mpo_score": 0.74, "caco2_papp_1e6": 2.4, "herg_ic50_um": 14.2},
    )

    # First write an intentionally incomplete draft missing the relay code to trigger Cycle 1 CORRECTION_REQUIRED
    finding_wo3_path = workspace_dir / "findings/medicinal-chemistry/mrtx1133-sar-admet.md"
    finding_wo3_path.write_text(
        f"# MRTX1133 SAR & ADMET Profile ({wo3_id}-r1)\n\n"
        "## Summary\n"
        "Initial draft without mandatory relay tag.\n\n"
        "## Key Findings\n"
        "- MPO score is 0.74 {source: raw/admet/MRTX1133.predict.json $.mpo_score}.\n",
        encoding="utf-8",
    )
    # Trigger Cycle 1 validation -> returns CORRECTION_REQUIRED and transitions validation_failed -> in_progress
    pde_validate_and_gate(wo3_id, run3_id, project_dir=str(workspace_dir))

    # Now write the corrected Layer 1 report addressing the relay & all checks
    finding_wo3_path.write_text(
        f"# MRTX1133 SAR & ADMET Profile ({wo3_id}-r1)\n\n"
        "## Summary\n"
        f"Completed 3D conformer generation, BRICS fragment SAR decomposition, and 5-axis ADMET profiling for `{wo3_id}-r1`. "
        "MRTX1133 achieves an MPO score of 0.74 {source: raw/admet/MRTX1133.predict.json $.mpo_score} with molecular weight 600.6 "
        "{source: raw/admet/MRTX1133.predict.json $.mw} Da.\n\n"
        "## Key Findings\n"
        "- **BRICS Pharmacophore Decomposition**: Identified 4 core fragments "
        "{source: raw/sar/MRTX1133_series.brics.json $.n_fragments}, led by the diazabicyclooctane Asp12 salt-bridge warhead "
        "contributing -4.8 {source: raw/sar/MRTX1133_series.brics.json $.fragments[0].kd_contribution_kcal} kcal/mol.\n"
        "- **5-Axis ADMET Profile**: Human liver microsomal half-life is 68.0 "
        "{source: raw/admet/MRTX1133.predict.json $.predictions.hlm_t12_min} min and hERG IC50 is 14.2 "
        "{source: raw/admet/MRTX1133.predict.json $.predictions.herg_ic50_um} uM, while Caco-2 permeability is 2.4 "
        "{source: raw/admet/MRTX1133.predict.json $.predictions.caco2_papp_1e6} x 10^-6 cm/s.\n"
        "- **Relay: `LOW_ORAL_PERMEABILITY_PRODRUG_EVAL`** — Evaluate phenolic pivaloyloxymethyl prodrugs to boost oral bioavailability above 11.5%.\n\n"
        "## Verdict\n"
        "**PASS WITH WARNINGS** — Potent G12D scaffold with clean CYP/hERG profile; optimize permeability in Cycle 2.\n\n"
        "## Evidence\n"
        "- [MRTX1133 3D Conformer](../../raw/compounds/MRTX1133.3d.sdf)\n"
        "- [MRTX1133 BRICS SAR](../../raw/sar/MRTX1133_series.brics.json)\n"
        "- [MRTX1133 ADMET Radar](../../raw/admet/MRTX1133.predict.json)\n\n"
        "## Implications\n"
        "Advance MRTX1133 to Switch-II docking and contact mapping while initiating phenolic prodrug synthesis.\n",
        encoding="utf-8",
    )
    pde_validate_and_gate(wo3_id, run3_id, project_dir=str(workspace_dir))
    pde_exec(f"workorder accept {wo3_id} --json", project_dir=str(workspace_dir), auto_refresh_dashboard=False)

    # ------------------------------------------------------------------
    # WO-004: Computational Chemist (Docking Poses, Scores & Contact Map)
    # ------------------------------------------------------------------
    wo4 = pde_dispatch_workorder(
        {
            "decision_question": "Dock MRTX1133 into KRAS G12D Switch-II pocket and quantify Asp12 salt-bridge and His95/Tyr96 contacts.",
            "requested_role": "computational-chemist",
            "stage": 2,
            "cycle": 1,
            "deliverables": {
                "layer_0_classes": ["pde.docking", "pde.bioactivity"],
                "layer_1": ["findings/computational-chemistry/mrtx1133-siip-docking.md"],
            },
        },
        project_dir=str(workspace_dir),
    )
    wo4_id, run4_id = wo4["work_order_id"], wo4["run_id"]

    _write_layer0_with_provenance(
        workspace_dir,
        "raw/docking/MRTX1133_SIIP.docking_result.json",
        {
            "ligand": "MRTX1133",
            "receptor": "KRAS_G12D",
            "pocket_id": "POCKET_1_SIIP",
            "top_affinity_kcal_mol": -11.4,
            "wt_affinity_kcal_mol": -7.8,
            "selectivity_ddg_kcal_mol": -3.6,
            "poses": [
                {"pose_rank": 1, "affinity_kcal_mol": -11.4, "rmsd_lb": 0.0, "rmsd_ub": 0.0, "asp12_salt_bridge_dist_a": 2.74},
                {"pose_rank": 2, "affinity_kcal_mol": -10.6, "rmsd_lb": 1.12, "rmsd_ub": 1.48, "asp12_salt_bridge_dist_a": 2.91},
                {"pose_rank": 3, "affinity_kcal_mol": -9.8, "rmsd_lb": 2.05, "rmsd_ub": 2.64, "asp12_salt_bridge_dist_a": 3.28},
                {"pose_rank": 4, "affinity_kcal_mol": -9.1, "rmsd_lb": 3.14, "rmsd_ub": 4.02, "asp12_salt_bridge_dist_a": 3.85},
            ],
        },
        wo_id=wo4_id,
        command="pde docking run MRTX1133 --receptor raw/structures/KRAS_G12D.cif --json",
        threshold_set="docking-v1",
        verdict="pass",
        summary="Top pose achieves -11.4 kcal/mol in KRAS G12D SII-P with 2.74 A Asp12 salt bridge and -3.6 kcal/mol selectivity over WT.",
        thresholds_applied={"max_affinity_kcal_mol": -8.5, "max_salt_bridge_dist_a": 3.2},
        mandatory_relays=[
            {
                "code": "SIIP_POSE1_SALT_BRIDGE_CONFIRMED",
                "target_role": "experimental-biologist",
                "detail": "Confirm Asp12 salt-bridge dependence via SPR against KRAS G12D vs G12V/WT.",
            }
        ],
        metrics={"top_affinity_kcal_mol": -11.4, "selectivity_ddg_kcal_mol": -3.6},
    )

    _write_layer0_with_provenance(
        workspace_dir,
        "raw/docking/KRAS_G12D.receptor.pdbqt",
        (
            "REMARK  Receptor KRAS_G12D Switch-II Pocket\n"
            "ATOM      1  N   ASP A  12      12.410  18.220   9.140  1.00 93.40    -0.350 NA\n"
            "ATOM      2  CA  ASP A  12      13.520  19.010   9.650  1.00 93.40     0.120 C\n"
            "ATOM      3  OD1 ASP A  12      15.780  20.340  10.580  1.00 91.50    -0.640 OA\n"
            "ATOM      4  OD2 ASP A  12      17.020  18.560  10.680  1.00 91.80    -0.640 OA\n"
            "ATOM      5  CA  ARG A  68      19.950  16.820  12.450  1.00 91.20     0.180 C\n"
            "ATOM      6  CA  HIS A  95      16.120  15.440  11.210  1.00 94.10     0.140 C\n"
            "ATOM      7  CA  TYR A  96      15.280  16.890  13.640  1.00 94.60     0.110 C\n"
            "TER\n"
        ),
        wo_id=wo4_id,
        command="pde docking prepare-receptor raw/structures/KRAS_G12D.cif --json",
        threshold_set="docking-v1",
        verdict="pass",
        summary="Prepared PDBQT receptor for KRAS G12D.",
        thresholds_applied={},
        mandatory_relays=[],
    )

    _write_layer0_with_provenance(
        workspace_dir,
        "raw/docking/MRTX1133_SIIP.poses.pdbqt",
        (
            "MODEL 1\n"
            "REMARK VINA RESULT:   -11.4      0.000      0.000\n"
            "HETATM    1  N1  UNL     1      15.120  19.450  10.820  1.00  0.00    -0.420 NA\n"
            "HETATM    2  C2  UNL     1      16.340  18.890  11.210  1.00  0.00     0.210 A\n"
            "HETATM    3  C3  UNL     1      17.450  19.620  11.880  1.00  0.00     0.150 A\n"
            "HETATM    4  N4  UNL     1      17.310  20.980  12.140  1.00  0.00    -0.380 NA\n"
            "HETATM    5  F1  UNL     1      19.820  19.610  12.890  1.00  0.00    -0.210 F\n"
            "ENDMDL\n"
        ),
        wo_id=wo4_id,
        command="pde docking poses MRTX1133 --json",
        threshold_set="docking-v1",
        verdict="pass",
        summary="Top Vina docking poses for MRTX1133 in KRAS G12D SII-P.",
        thresholds_applied={},
        mandatory_relays=[],
    )

    _write_layer0_with_provenance(
        workspace_dir,
        "raw/docking/MRTX1133_SIIP.contacts.json",
        {
            "ligand": "MRTX1133",
            "receptor": "KRAS_G12D",
            "n_contacts": 6,
            "contacts": [
                {"residue": "ASP12", "interaction": "Salt Bridge / Ionic H-Bond", "distance_a": 2.74, "energy_kcal": -4.8},
                {"residue": "GLY60", "interaction": "Backbone H-Bond", "distance_a": 2.98, "energy_kcal": -1.9},
                {"residue": "GLU62", "interaction": "Water-Mediated H-Bond", "distance_a": 3.12, "energy_kcal": -1.6},
                {"residue": "ARG68", "interaction": "Cation-Pi / Stacking", "distance_a": 3.54, "energy_kcal": -2.1},
                {"residue": "HIS95", "interaction": "Aromatic Groove Contact", "distance_a": 3.68, "energy_kcal": -1.8},
                {"residue": "TYR96", "interaction": "Pi-Pi T-Stacking", "distance_a": 3.72, "energy_kcal": -2.4},
            ],
        },
        wo_id=wo4_id,
        command="pde docking contacts raw/docking/MRTX1133_SIIP.poses.pdbqt --json",
        threshold_set="docking-v1",
        verdict="pass",
        summary="6 key protein-ligand interactions identified, anchored by the 2.74 A Asp12 bidentate salt bridge.",
        thresholds_applied={"min_contacts": 4},
        mandatory_relays=[],
        metrics={"n_contacts": 6, "asp12_distance_a": 2.74},
    )

    _write_layer0_with_provenance(
        workspace_dir,
        "raw/bioactivity/KRAS_G12D_panel.json",
        {
            "compound": "MRTX1133",
            "kras_g12d_kd_nm": 0.2,
            "kras_wt_kd_nm": 145.0,
            "selectivity_fold": 725.0,
            "p_erk_ic50_nm": 1.8,
            "on_target": {"target": "KRAS G12D", "ic50_nm": 0.2},
            "off_targets": [
                {"target": "KRAS WT", "ic50_nm": 145.0},
                {"target": "HRAS WT", "ic50_nm": 520.0},
                {"target": "NRAS WT", "ic50_nm": 610.0},
            ],
            "selectivity_ratios": [
                {"off_target": "KRAS WT", "selectivity_fold": 725.0, "margin_class": "high (>100x)"},
                {"off_target": "HRAS WT", "selectivity_fold": 2600.0, "margin_class": "high (>100x)"},
                {"off_target": "NRAS WT", "selectivity_fold": 3050.0, "margin_class": "high (>100x)"},
            ],
        },
        wo_id=wo4_id,
        command="pde assay fetch MRTX1133 --json",
        threshold_set="bioactivity-v1",
        verdict="pass",
        summary="SPR confirms KRAS G12D Kd=0.2 nM with 725-fold selectivity over wild-type KRAS (Kd=145 nM).",
        thresholds_applied={"min_selectivity_fold": 50.0},
        mandatory_relays=[],
        metrics={"kras_g12d_kd_nm": 0.2, "selectivity_fold": 725.0},
    )

    (workspace_dir / "findings/computational-chemistry/mrtx1133-siip-docking.md").write_text(
        f"# MRTX1133 Switch-II Docking & Selectivity Analysis ({wo4_id}-r1)\n\n"
        "## Summary\n"
        f"Executed induced-fit docking, residue contact profiling, and SPR bioactivity integration for `{wo4_id}-r1`. "
        "MRTX1133 docks into `POCKET_1_SIIP` with a top binding score of -11.4 "
        "{source: raw/docking/MRTX1133_SIIP.docking_result.json $.top_affinity_kcal_mol} kcal/mol and "
        "experimental KRAS G12D Kd of 0.2 {source: raw/bioactivity/KRAS_G12D_panel.json $.kras_g12d_kd_nm} nM.\n\n"
        "## Key Findings\n"
        "- **Asp12 Salt-Bridge Geometry**: Pose 1 positions the protonated bicyclic piperazine at 2.74 "
        "{source: raw/docking/MRTX1133_SIIP.contacts.json $.contacts[0].distance_a} A from Asp12 OD1/OD2 across 6 "
        "{source: raw/docking/MRTX1133_SIIP.contacts.json $.n_contacts} total pocket contacts.\n"
        "- **Mutant Selectivity**: Wild-type selectivity reaches 725.0 "
        "{source: raw/bioactivity/KRAS_G12D_panel.json $.selectivity_fold} fold (ddG = -3.6 "
        "{source: raw/docking/MRTX1133_SIIP.docking_result.json $.selectivity_ddg_kcal_mol} kcal/mol), "
        "satisfying the `ESSENTIAL_GENE_WT_SPARING_REQUIRED` constraint.\n"
        "- **Relay: `SIIP_POSE1_SALT_BRIDGE_CONFIRMED`** — Proceed to cellular pERK and resistance tournament evaluation.\n\n"
        "## Verdict\n"
        "**PASS** — Structural and biophysical selectivity criteria (>50x WT sparing) are exceeded at 725x.\n\n"
        "## Evidence\n"
        "- [MRTX1133 Docking Scores](../../raw/docking/MRTX1133_SIIP.docking_result.json)\n"
        "- [MRTX1133 Contact Map](../../raw/docking/MRTX1133_SIIP.contacts.json)\n"
        "- [KRAS G12D SPR Panel](../../raw/bioactivity/KRAS_G12D_panel.json)\n\n"
        "## Implications\n"
        "Lock the Asp12 diazabicyclooctane + 3-hydroxynaphthyl core for Stage 3 lead optimization.\n",
        encoding="utf-8",
    )
    pde_validate_and_gate(wo4_id, run4_id, project_dir=str(workspace_dir))
    pde_exec(f"workorder accept {wo4_id} --json", project_dir=str(workspace_dir), auto_refresh_dashboard=False)

    # ------------------------------------------------------------------
    # WO-005: Hypex Supervisor (Co-Scientist / Hypex ELO Tournament)
    # ------------------------------------------------------------------
    wo5 = pde_dispatch_workorder(
        {
            "decision_question": "Run Co-Scientist / Hypex ELO tournament to rank rational combination & secondary resistance hypotheses for KRAS G12D inhibition.",
            "requested_role": "hypex-supervisor",
            "stage": 2,
            "cycle": 2,
            "resource_class": "hypex-supervisor",
            "deliverables": {
                "layer_0_classes": ["pde.hypotheses"],
                "layer_1": ["findings/computational-biology/kras-hypex-tournament.md"],
            },
        },
        project_dir=str(workspace_dir),
    )
    wo5_id, run5_id = wo5["work_order_id"], wo5["run_id"]

    _write_layer0_with_provenance(
        workspace_dir,
        "raw/hypotheses/kras_resistance.tournament.json",
        {
            "research_goal": "Overcome adaptive RTK/SHP2 feedback and secondary Switch-II mutations under KRAS G12D inhibition in PDAC",
            "n_hypotheses": 4,
            "n_matches": 24,
            "top_elo": 1648,
            "hypotheses": [
                {
                    "id": "HYP-001",
                    "title": "Dual MRTX1133 + SHP2 (RMC-4630) pulsatile blockade prevents adaptive RTK-driven WT RAS reactivation",
                    "elo": 1648,
                    "wins": 11,
                    "losses": 1,
                    "win_rate": 0.917,
                    "novelty_score": 8.8,
                    "testability_score": 9.4,
                    "scores": {"overall": 9.2, "correctness": 9.5, "novelty": 8.8, "testability": 9.4, "safety": 9.1},
                    "evolution_operator": "combine",
                    "parent_ids": ["HYP-001a", "HYP-001b"],
                    "cluster_id": "CL-RTK-SHP2",
                    "rationale": "RTK-SHP2-SOS1 nucleotide exchange reactivates WT HRAS/NRAS within 48h of G12D suppression; intermittent SHP2 co-inhibition collapses pERK rebound while sparing GI mucosa.",
                },
                {
                    "id": "HYP-002",
                    "title": "C2-fluorinated pyrrolizidine C-O-C conformational lock mitigates Tyr96Asp/His95Gln Switch-II groove resistance",
                    "elo": 1572,
                    "wins": 8,
                    "losses": 4,
                    "win_rate": 0.667,
                    "novelty_score": 9.1,
                    "testability_score": 8.9,
                    "scores": {"overall": 8.9, "correctness": 8.8, "novelty": 9.1, "testability": 8.9, "safety": 9.0},
                    "evolution_operator": "ground",
                    "parent_ids": ["HYP-002-seed"],
                    "cluster_id": "CL-SIIP-LOCK",
                    "rationale": "Pre-organizing the C2 sidechain reduces entropic penalty when His95 hydrogen bonding is lost in acquired resistance clones.",
                },
                {
                    "id": "HYP-003",
                    "title": "Phenolic pivaloyloxymethyl (POM) prodrug of MRTX1133 masks naphthol HBD to achieve >35% oral bioavailability",
                    "elo": 1510,
                    "wins": 4,
                    "losses": 8,
                    "win_rate": 0.333,
                    "novelty_score": 7.9,
                    "testability_score": 9.2,
                    "scores": {"overall": 8.4, "correctness": 8.7, "novelty": 7.9, "testability": 9.2, "safety": 8.5},
                    "evolution_operator": "simplify",
                    "parent_ids": [],
                    "cluster_id": "CL-PRODRUG",
                    "rationale": "Masking the 3-hydroxynaphthyl donor lowers TPSA from 93.5 to 79.2 A^2 and increases Caco-2 Papp >3-fold.",
                },
                {
                    "id": "HYP-004",
                    "title": "ULK1 autophagy co-inhibition synergizes with G12D blockade in nutrient-deprived PDAC organoids",
                    "elo": 1412,
                    "wins": 1,
                    "losses": 11,
                    "win_rate": 0.083,
                    "novelty_score": 7.2,
                    "testability_score": 8.1,
                    "scores": {"overall": 7.6, "correctness": 7.8, "novelty": 7.2, "testability": 8.1, "safety": 7.9},
                    "evolution_operator": "oob",
                    "parent_ids": [],
                    "cluster_id": "CL-AUTOPHAGY",
                    "rationale": "PDAC cells upregulate macropinocytosis and autophagy upon MAPK pathway suppression.",
                },
            ],
            "matches": [
                {
                    "hypothesis_a": "HYP-001",
                    "hypothesis_b": "HYP-002",
                    "winner": "HYP-001",
                    "rationale": "HYP-001 directly addresses adaptive WT RAS feedback observed within 48h in PDAC models using clinically available SHP2 inhibitors.",
                },
                {
                    "hypothesis_a": "HYP-002",
                    "hypothesis_b": "HYP-003",
                    "winner": "HYP-002",
                    "rationale": "Conformational C2 lock directly overcomes on-target Switch-II groove resistance mutations.",
                },
            ],
        },
        wo_id=wo5_id,
        command="pde hypex tournament run --goal 'KRAS G12D resistance and optimization' --json",
        threshold_set="hypex-v1",
        verdict="pass",
        summary="Co-Scientist / Hypex tournament (24 matches, 4 hypotheses) ranks HYP-001 (MRTX1133 + SHP2 pulsatile blockade, ELO 1648) #1.",
        thresholds_applied={"min_top_elo": 1550, "min_matches": 12},
        mandatory_relays=[
            {
                "code": "HYPEX_TOP_RANKED_SHP2_COMBO",
                "target_role": "experimental-biologist",
                "detail": "Validate HYP-001 (ELO 1648) in AsPC-1 and GP2d PDAC lines with 72h pERK rebound readout.",
            }
        ],
        metrics={"top_elo": 1648, "n_hypotheses": 4, "n_matches": 24},
    )

    (workspace_dir / "findings/computational-biology/kras-hypex-tournament.md").write_text(
        f"# Co-Scientist / Hypex Hypothesis Tournament Report ({wo5_id}-r1)\n\n"
        "## Summary\n"
        f"Executed a 24-match {wo5_id}-r1 Co-Scientist / Hypex ELO tournament across 4 "
        "{source: raw/hypotheses/kras_resistance.tournament.json $.n_hypotheses} competing hypotheses. "
        "`HYP-001` achieved the #1 tournament ELO rating of 1648 "
        "{source: raw/hypotheses/kras_resistance.tournament.json $.top_elo} (11-1 record, win rate 0.917 "
        "{source: raw/hypotheses/kras_resistance.tournament.json $.hypotheses[0].win_rate}).\n\n"
        "## Key Findings\n"
        "- **#1 Ranked Hypothesis (`HYP-001`, ELO 1648)**: Pulsatile MRTX1133 + SHP2 co-inhibition suppresses RTK-driven WT RAS feedback.\n"
        "- **#2 Ranked Hypothesis (`HYP-002`, ELO 1572 {source: raw/hypotheses/kras_resistance.tournament.json $.hypotheses[1].elo})**: "
        "Conformational C2-pyrrolizidine lock retains potency against Tyr96Asp/His95Gln Switch-II mutations.\n"
        "- **Relay: `HYPEX_TOP_RANKED_SHP2_COMBO`** — Prioritize AsPC-1 72h pERK rebound combination matrix in Stage 3.\n\n"
        "## Verdict\n"
        "**PASS** — Tournament converged with clear separation (ELO 1648 vs 1572) and actionable experimental relays.\n\n"
        "## Evidence\n"
        "- [Hypex Tournament Leaderboard](../../raw/hypotheses/kras_resistance.tournament.json)\n\n"
        "## Implications\n"
        "Advance `HYP-001` (combination biology) and `HYP-002`/`HYP-003` (Cycle 2 chemistry) into Stage 3 nominations.\n",
        encoding="utf-8",
    )
    pde_validate_and_gate(wo5_id, run5_id, project_dir=str(workspace_dir))
    pde_exec(f"workorder accept {wo5_id} --json", project_dir=str(workspace_dir), auto_refresh_dashboard=False)

    # ------------------------------------------------------------------
    # Populate Layer 3 Concepts, Assessments, Decisions & Retrospectives
    # ------------------------------------------------------------------
    for dname in ("concepts", "assessments", "decisions", "retrospectives"):
        (workspace_dir / dname).mkdir(parents=True, exist_ok=True)

    (workspace_dir / "concepts/IC-001.yaml").write_text(
        "id: IC-001\n"
        "title: Non-Covalent KRAS G12D Switch-II Pocket Inhibitor (MRTX1133 Core)\n"
        "target: KRAS G12D\n"
        "modality: small_molecule\n"
        "indication: Pancreatic Ductal Adenocarcinoma (PDAC)\n"
        "mechanism: Asp12 bidentate salt-bridge stabilization of GDP-bound KRAS G12D Switch-II pocket\n"
        "status: active\n",
        encoding="utf-8",
    )

    (workspace_dir / "assessments/AR-001.yaml").write_text(
        "id: AR-001\n"
        "concept_id: IC-001\n"
        "category: Stage 1 Target & Pocket Tractability\n"
        "verdict: pass\n"
        "summary: Switch-II pocket druggability 0.84 (542.6 A^3) and 725x G12D/WT selectivity satisfy Stage 1 gate.\n",
        encoding="utf-8",
    )

    (workspace_dir / "decisions/DR-001.yaml").write_text(
        "id: DR-001\n"
        "stage: Stage 2 -> Stage 3\n"
        "outcome: GO_TO_STAGE_3\n"
        "rationale: All 5 work orders mechanically validated and scientifically accepted; 725x WT selectivity mitigates essentiality.\n"
        "decided_at: 2026-10-07T14:30:00Z\n",
        encoding="utf-8",
    )

    (workspace_dir / "retrospectives/medicinal-chemist-retro.md").write_text(
        "# Medicinal Chemist Subagent Retrospective (`WO-003`)\n\n"
        "- **Cycle 1 Mechanical Correction**: Initial Layer 1 draft omitted `LOW_ORAL_PERMEABILITY_PRODRUG_EVAL`; "
        "Check #6 (`relay_coverage`) caught the omission and triggered an automated retry.\n"
        "- **Resolution**: Added explicit phenolic POM prodrug recommendation and verified all `{source:}` JSONPaths.\n",
        encoding="utf-8",
    )

    # ------------------------------------------------------------------
    # Populate Layer 2 Program State & Layer 4 Executive Summary
    # ------------------------------------------------------------------
    (workspace_dir / "program-state/active-series.md").write_text(
        "# Active Chemical Series\n\n"
        "## Series 1: 8-Fluoropyrido[4,3-d]pyrimidine Switch-II Inhibitors (`MRTX1133` Core)\n"
        "- **Status**: Active Lead Series (Stage 2 -> Stage 3 Transition)\n"
        "- **Target Engagement**: KRAS G12D $K_d = 0.2\\text{ nM}$, WT KRAS $K_d = 145\\text{ nM}$ ($725\\times$ selectivity)\n"
        "- **Docking Score**: $-11.4\\text{ kcal/mol}$ in `POCKET_1_SIIP` ($2.74\\text{ \\AA}$ Asp12 salt bridge)\n"
        "- **Key Optimization Vector**: Phenolic ester prodrug (`HYP-003`) to raise oral bioavailability from $11.5\\%$ to $>35\\%$.\n",
        encoding="utf-8",
    )

    (workspace_dir / "program-state/liability-tracker.md").write_text(
        "# Liability Tracker\n\n"
        "## L-1: Wild-Type KRAS Essentiality in GI Mucosa & Heart\n"
        "- **Severity**: High\n"
        "- **Status**: mitigated\n"
        "- **Evidence**: gnomAD `pLI = 0.98`, `LOEUF = 0.24`; GTEx Colon `48.5 TPM`.\n"
        "- **Mitigation**: Achieved $725\\times$ biochemical selectivity for G12D over WT via Asp12 salt-bridge warhead (`WO-004`).\n\n"
        "## L-2: Low Oral Permeability of Zwitterionic/Phenolic Lead (`MRTX1133`)\n"
        "- **Severity**: Moderate\n"
        "- **Status**: open\n"
        "- **Evidence**: Caco-2 $P_{app} = 2.4 \\times 10^{-6}\\text{ cm/s}$, rodent oral $F = 11.5\\%$ (`WO-003`).\n"
        "- **Mitigation**: Phenolic POM prodrug synthesis queued (`HYP-003`).\n",
        encoding="utf-8",
    )

    (workspace_dir / "program-state/decision-log.md").write_text(
        "# Program Decision Log\n\n"
        "- **DEC-001 (Stage 1 Charter)**: Initiated KRAS G12D selective non-covalent Switch-II inhibitor program for PDAC.\n"
        "- **DEC-002 (WT Sparing Gate)**: Enforced $\\ge 50\\times$ G12D/WT selectivity gate following `WO-001` (`pLI = 0.98`).\n"
        "- **DEC-003 (Lead Series Selection)**: Accepted `WO-002`, `WO-003`, and `WO-004` validating `MRTX1133` ($725\\times$ selective, $-11.4\\text{ kcal/mol}$).\n"
        "- **DEC-004 (Co-Scientist Combination Nomination)**: Adopted `HYP-001` (ELO 1648, pulsatile SHP2 combination) from `WO-005`.\n",
        encoding="utf-8",
    )

    (workspace_dir / "program-state/open-questions.md").write_text(
        "# Open Scientific Questions\n\n"
        "1. **OQ-001**: Does the phenolic POM prodrug (`HYP-003`) undergo rapid pre-systemic cleavage in enterocytes vs portal blood?\n"
        "2. **OQ-002**: Does the C2-fluorinated pyrrolizidine conformational lock (`HYP-002`) retain $<5\\text{ nM}$ cellular potency against KRAS G12D/Y96D double mutants?\n",
        encoding="utf-8",
    )

    (workspace_dir / "executive/program-summary.md").write_text(
        "# Executive Program Summary — KRAS G12D Selective Inhibitor (`KRAS-G12D-Selective-Inhibitor`)\n\n"
        "## Stage 2 Gate Readiness: **GO TO STAGE 3**\n\n"
        "| Dimension | Metric | Target Gate | Observed | Status |\n"
        "|---|---|---|---|---|\n"
        "| **Human Genetics (`WO-001`)** | PDAC OpenTargets Score / pLI | $\\ge 0.70$ | $0.94$ (`pLI = 0.98`) | PASS (WT-sparing required) |\n"
        "| **Pocket Druggability (`WO-002`)** | Switch-II SII-P Druggability | $\\ge 0.60$ | $0.84$ ($542.6\\text{ \\AA}^3$) | PASS |\n"
        "| **Binding & Selectivity (`WO-004`)** | G12D $K_d$ / WT Selectivity | $< 5\\text{ nM}$ / $\\ge 50\\times$ | $0.2\\text{ nM}$ / $725\\times$ | PASS |\n"
        "| **ADMET & MPO (`WO-003`)** | MPO Score / HLM $t_{1/2}$ | $\\ge 0.65$ / $> 45\\text{ min}$ | $0.74$ / $68\\text{ min}$ | PASS WITH WARNINGS ($P_{app}=2.4$) |\n"
        "| **Co-Scientist Tournament (`WO-005`)** | Top Hypothesis ELO | $\\ge 1550$ | $1648$ (`HYP-001`) | PASS |\n",
        encoding="utf-8",
    )

    # Render the self-contained Interactive Scientific Dashboard in the workspace (dashboard.html)
    ws_dash = pde_render_dashboard(project_dir=str(workspace_dir))

    return {
        "workspace_dir": str(workspace_dir),
        "workspace_dashboard": ws_dash.get("output_path"),
        "summary_metrics": ws_dash.get("summary_metrics"),
    }

