# KRAS Genetic Constraint & Tissue Expression Assessment (WO-001-r1)

## Summary
Executed human genetic constraint and normal tissue transcriptomic profiling for `WO-001-r1`. KRAS exhibits extreme loss-of-function intolerance in gnomAD with pLI of 0.98 {source: raw/genomics/KRAS.gnomad-constraint.json $.constraint.pLI} and LOEUF of 0.24 {source: raw/genomics/KRAS.gnomad-constraint.json $.constraint.loeuf}.

## Key Findings
- **Missense & LoF Constraint**: Missense Z-score is 3.42 {source: raw/genomics/KRAS.gnomad-constraint.json $.constraint.mis_z}, confirming strong purifying selection.
- **Oncology Driver Evidence**: Pancreatic adenocarcinoma association score is 0.94 {source: raw/genomics/KRAS.gnomad-constraint.json $.disease_associations[0].overall_score}.
- **Normal Tissue Expression (GTEx)**: Peak expression occurs in Colon - Transverse at 48.5 {source: raw/gtex/KRAS.tissue.json $.max_tpm} TPM and Pancreas at 22.4 {source: raw/gtex/KRAS.tissue.json $.tissues[3].median_tpm} TPM.
- **Relay: `ESSENTIAL_GENE_WT_SPARING_REQUIRED`** — Medicinal chemistry and docking must enforce >=50x G12D over WT selectivity.
- **Relay: `GI_MUCOSA_WT_EXPRESSION_MONITOR`** — Preclinical toxicology must monitor GI mucosa.

## Verdict
**GO WITH CAUTION** — Proceed with non-covalent Switch-II pocket inhibitors specifically engaging Asp12.

## Evidence
- [KRAS gnomAD Constraint](../../raw/genomics/KRAS.gnomad-constraint.json)
- [KRAS GTEx Expression](../../raw/gtex/KRAS.tissue.json)

## Implications
Wild-type KRAS sparing is the primary design constraint for Stage 2 hit-to-lead.
