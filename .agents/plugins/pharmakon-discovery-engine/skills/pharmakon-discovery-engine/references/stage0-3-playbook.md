# PDE Stage 0–3 Playbook & 10-Check Validation Reference

## Stage Gates & Cohort Playbook

### Stage 0 — Rapid Target Triage
- **Objective**: Rapid Go/No-Go screening across human genetics (`gnomAD`, `OpenTargets`), structure availability (`PDB`, `AlphaFold DB`), and clinical landscape (`ClinicalTrials.gov`, `ChEMBL`).
- **Primary Command**: `pde triage score <GENE> --indication <EFO_ID> --json` followed by `pde triage analyze <GENE> --json`.
- **Gate Criterion**: Composite Stage 0 Triage Score $\ge 0.60$ with no unmitigated Critical genetic safety liabilities (`pLI >= 0.90` in essential housekeeping tissues without therapeutic window).

### Stage 1 — Target Validation & Tractability
- **Specialists**:
  - `pde-computational-biologist`: `genetics`, `gwas`, `expression`, `gtex`, `pathway`
  - `pde-structural-biologist`: `alphafold`, `structure`, `pocket`, `conservation`
  - `pde-preclinical-toxicologist`: `tox`, `expression` (on-target safety & essentiality)
  - `pde-regulatory-scientist`: `trials`, `patent`, `differentiation`
- **Gate Skill**: `stage1-gate-evaluation` (`findings/executive/stage1-gate-scorecard.md`).

### Stage 2 — Hit Identification & Virtual Screening
- **Specialists**:
  - `pde-medicinal-chemist`: `compound`, `similar`, `pubchem`, `analog`
  - `pde-computational-chemist`: `docking`, `screen`, `structure_screen`
  - `pde-admet-dmpk-scientist`: `admet` (baseline tier-1 ADMET triage)

### Stage 3 — Hit-to-Lead & Lead Optimization
- **Specialists**:
  - `pde-medicinal-chemist`: `mmp`, `mpo`, `retro` (SAR series & multipartite property optimization)
  - `pde-admet-dmpk-scientist`: `admet`, `pk` (in vivo PK, clearance, bioavailability)
  - `pde-experimental-biologist`: `assay`, `selectivity`
  - `pde-preclinical-toxicologist`: `tox` (hERG, Ames, DILI, off-target safety)

---

## The 10 Mechanical Validation Checks (`pde validate check <WO-ID>`)

| # | Check Name | Defect Kind | Overridable? | Requirement |
|---|---|---|---|---|
| 1 | `deliverables_exist` | `COMPLETENESS` | No | All declared `layer_0_classes` and `layer_1` files exist and are non-empty. |
| 2 | `report_headings` | `FORMAT` | Yes | Every Layer 1 Markdown report has `## Summary`, `## Verdict`, and `## Evidence` headings and cites `WO-NNN` or `r<rev>`. |
| 3 | `paths_resolve` | `COMPLETENESS` | Yes | Every `raw/...` and `findings/...` path mentioned in Layer 1 reports resolves on disk. |
| 4 | `provenance_valid` | `DATA_INTEGRITY` | Yes | Every Layer 0 artifact has a valid `.meta.json` sidecar whose `output_sha256` matches the file on disk. |
| 5 | `analysis_citations` | `DATA_INTEGRITY` | Yes | Every Layer 0 artifact has a `.analysis.json` sidecar and is cited in a Layer 1 report. |
| 6 | `relay_coverage` | `COMPLETENESS` | Yes | Every `mandatory_relays` code in `.analysis.json` appears in a Layer 1 report (`**Relay: \`<code>\`**`). |
| 7 | `version_policy` | `CONSISTENCY` | No | All `.meta.json` sidecars match the active `tools/ENV_VERSION` (`cli_version`). |
| 8 | `findings_integrity` | `DATA_INTEGRITY` | No | Prior findings checksums in `.pde/control/contexts/` have not been retroactively mutated. |
| 9 | `source_tags_resolve` | `DATA_INTEGRITY` | No | Every `{source: raw/<path>#$.json.path}` inline tag resolves to the cited value in Layer 0 JSON. |
| 10 | `unrecognized_json` | `COMPLETENESS` | No | No `.json` files exist in `raw/` without a `.meta.json` sidecar (catches hand-crafted JSON). |
