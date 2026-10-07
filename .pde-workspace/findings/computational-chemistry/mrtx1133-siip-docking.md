# MRTX1133 Switch-II Docking & Selectivity Analysis (WO-004-r1)

## Summary
Executed induced-fit docking, residue contact profiling, and SPR bioactivity integration for `WO-004-r1`. MRTX1133 docks into `POCKET_1_SIIP` with a top binding score of -11.4 {source: raw/docking/MRTX1133_SIIP.docking_result.json $.top_affinity_kcal_mol} kcal/mol and experimental KRAS G12D Kd of 0.2 {source: raw/bioactivity/KRAS_G12D_panel.json $.kras_g12d_kd_nm} nM.

## Key Findings
- **Asp12 Salt-Bridge Geometry**: Pose 1 positions the protonated bicyclic piperazine at 2.74 {source: raw/docking/MRTX1133_SIIP.contacts.json $.contacts[0].distance_a} A from Asp12 OD1/OD2 across 6 {source: raw/docking/MRTX1133_SIIP.contacts.json $.n_contacts} total pocket contacts.
- **Mutant Selectivity**: Wild-type selectivity reaches 725.0 {source: raw/bioactivity/KRAS_G12D_panel.json $.selectivity_fold} fold (ddG = -3.6 {source: raw/docking/MRTX1133_SIIP.docking_result.json $.selectivity_ddg_kcal_mol} kcal/mol), satisfying the `ESSENTIAL_GENE_WT_SPARING_REQUIRED` constraint.
- **Relay: `SIIP_POSE1_SALT_BRIDGE_CONFIRMED`** — Proceed to cellular pERK and resistance tournament evaluation.

## Verdict
**PASS** — Structural and biophysical selectivity criteria (>50x WT sparing) are exceeded at 725x.

## Evidence
- [MRTX1133 Docking Scores](../../raw/docking/MRTX1133_SIIP.docking_result.json)
- [MRTX1133 Contact Map](../../raw/docking/MRTX1133_SIIP.contacts.json)
- [KRAS G12D SPR Panel](../../raw/bioactivity/KRAS_G12D_panel.json)

## Implications
Lock the Asp12 diazabicyclooctane + 3-hydroxynaphthyl core for Stage 3 lead optimization.
