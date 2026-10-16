# PkDE Stage 0-3 Playbook & 10-Check Validation Reference

## Preflight & Degraded-Mode Sandbox Contract (`pkde doctor --json`)

Before dispatching any Stage 0-3 Work Orders, run `./bin/pkde doctor --json` and inspect `"execution_mode"`:

- **`"full"`**: Outbound scientific APIs and local compute are both operational. Full Stage 0-3 workflows may proceed.
- **`"degraded_offline"`**: Outbound network is blocked in the current sandbox (`"network_reachable": false`).
  - **Prohibited in `degraded_offline`**: Never dispatch online-fetch Work Orders (`genetics`, `gwas`, `alphafold`, `pubchem`, `literature`, `trials`, `expression`, `gtex`, `geo`, `cellxgene`) and never create a Stage Gate Package (`stage1-gate-evaluation`) with `0/N` empty evidence slots caused by network unavailability.
  - **Allowed in `degraded_offline`**: Local-compute tools operating on user-provided files or SMILES (`pkde custom ingest/run/analyze`, `compound`, `admet`, `assay`, `selectivity`, `mmp`, `mpo`, `pk`, `tox`, `pocket`, `docking`).
  - **Fail-Fast Rule**: If the user's request requires online database retrieval and no local/custom data files are provided, halt immediately before creating any Work Orders and report `ENVIRONMENT_BLOCKED`.
- **`"blocked"`**: Core Python or provenance checks failed (`"ok": false`). Resolve the failed checks before running any commands.

---

## Stage Gates & Cohort Playbook

### Stage 0 -- Rapid Target Triage
- **Objective**: Rapid Go/No-Go screening across human genetics (`gnomAD`, `OpenTargets`), structure availability (`PDB`, `AlphaFold DB`), and clinical landscape (`ClinicalTrials.gov`, `ChEMBL`).
- **Primary Command**: `pkde triage score <GENE> --indication <EFO_ID> --json` followed by `pkde triage analyze <GENE> --json` (or `pkde structure-screen run` / `pkde manufacturing assess-stage0`).
- **Gate Criterion**: Composite Stage 0 Triage Score $\ge 0.60$ with no unmitigated Critical genetic safety liabilities (`pLI >= 0.90` in essential housekeeping tissues without therapeutic window).

### Stage 1 -- Target Validation & Tractability
- **Specialists**:
  - `pkde-computational-biologist`: `genetics`, `gwas`, `expression`, `gtex`, `pathway`, `custom`
  - `pkde-structural-biologist`: `alphafold`, `structure`, `pocket`, `conservation`
  - `pkde-preclinical-toxicologist`: `tox`, `expression` (on-target safety & essentiality)
  - `pkde-regulatory-scientist`: `trials`, `patent`, `differentiation`
- **Gate Skill**: `stage1-gate-evaluation` (`findings/executive/stage1-gate-scorecard.md`). Requires populated Layer 0/Layer 1 evidence; never evaluate a Stage 1 gate on empty evidence slots.

### Stage 2 -- Hit Identification & Virtual Screening
- **Specialists**:
  - `pkde-medicinal-chemist`: `compound`, `similar`, `pubchem`, `analog`, `custom`
  - `pkde-computational-chemist`: `docking`, `screen`, `structure_screen`, `custom`
  - `pkde-admet-dmpk-scientist`: `admet` (baseline tier-1 ADMET triage)

### Stage 3 -- Hit-to-Lead & Lead Optimization
- **Specialists**:
  - `pkde-medicinal-chemist`: `mmp`, `mpo`, `retro`, `custom` (SAR series & multipartite property optimization)
  - `pkde-admet-dmpk-scientist`: `admet`, `pk` (in vivo PK, clearance, bioavailability)
  - `pkde-experimental-biologist`: `assay`, `selectivity`, `custom`
  - `pkde-preclinical-toxicologist`: `tox` (hERG, Ames, DILI, off-target safety)

---

## The 10 Mechanical Validation Checks (`pkde validate check <WO-ID>`)

| # | Check Name | Defect Kind | Overridable? | Requirement |
|---|---|---|---|---|
| 1 | `deliverables_exist` | `COMPLETENESS` | No | All declared `layer_0_classes` and `layer_1` files exist and are non-empty. |
| 2 | `report_headings` | `FORMAT` | Yes | Every Layer 1 Markdown report has `## Summary`, `## Verdict`, and `## Evidence` headings and cites `WO-NNN` or `r<rev>`. |
| 3 | `paths_resolve` | `COMPLETENESS` | Yes | Every `raw/...` and `findings/...` path mentioned in Layer 1 reports resolves on disk. |
| 4 | `provenance_valid` | `DATA_INTEGRITY` | Yes | Every Layer 0 artifact has a valid `.meta.json` sidecar whose `output_sha256` matches the file on disk. |
| 5 | `analysis_citations` | `DATA_INTEGRITY` | Yes | Every Layer 0 artifact has a `.analysis.json` sidecar and is cited in a Layer 1 report. |
| 6 | `relay_coverage` | `COMPLETENESS` | Yes | Every `mandatory_relays` code in `.analysis.json` appears in a Layer 1 report (`**Relay: \`<code>\`**`). |
| 7 | `version_policy` | `CONSISTENCY` | No | All `.meta.json` sidecars match the active `tools/ENV_VERSION` (`cli_version`). |
| 8 | `findings_integrity` | `DATA_INTEGRITY` | No | Prior findings checksums in `.pkde/control/contexts/` have not been retroactively mutated. |
| 9 | `source_tags_resolve` | `DATA_INTEGRITY` | No | Every `{source: raw/<path>#$.json.path}` inline tag resolves to the cited value in Layer 0 JSON. |
| 10 | `unrecognized_json` | `COMPLETENESS` | No | No `.json` files exist in `raw/` without a `.meta.json` sidecar (catches hand-crafted JSON). |
