# MRTX1133 SAR & ADMET Profile (WO-003-r1)

## Summary
Completed 3D conformer generation, BRICS fragment SAR decomposition, and 5-axis ADMET profiling for `WO-003-r1`. MRTX1133 achieves an MPO score of 0.74 {source: raw/admet/MRTX1133.predict.json $.mpo_score} with molecular weight 600.6 {source: raw/admet/MRTX1133.predict.json $.mw} Da.

## Key Findings
- **BRICS Pharmacophore Decomposition**: Identified 4 core fragments {source: raw/sar/MRTX1133_series.brics.json $.n_fragments}, led by the diazabicyclooctane Asp12 salt-bridge warhead contributing -4.8 {source: raw/sar/MRTX1133_series.brics.json $.fragments[0].kd_contribution_kcal} kcal/mol.
- **5-Axis ADMET Profile**: Human liver microsomal half-life is 68.0 {source: raw/admet/MRTX1133.predict.json $.predictions.hlm_t12_min} min and hERG IC50 is 14.2 {source: raw/admet/MRTX1133.predict.json $.predictions.herg_ic50_um} uM, while Caco-2 permeability is 2.4 {source: raw/admet/MRTX1133.predict.json $.predictions.caco2_papp_1e6} x 10^-6 cm/s.
- **Relay: `LOW_ORAL_PERMEABILITY_PRODRUG_EVAL`** — Evaluate phenolic pivaloyloxymethyl prodrugs to boost oral bioavailability above 11.5%.

## Verdict
**PASS WITH WARNINGS** — Potent G12D scaffold with clean CYP/hERG profile; optimize permeability in Cycle 2.

## Evidence
- [MRTX1133 3D Conformer](../../raw/compounds/MRTX1133.3d.sdf)
- [MRTX1133 BRICS SAR](../../raw/sar/MRTX1133_series.brics.json)
- [MRTX1133 ADMET Radar](../../raw/admet/MRTX1133.predict.json)

## Implications
Advance MRTX1133 to Switch-II docking and contact mapping while initiating phenolic prodrug synthesis.
