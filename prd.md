# Product Requirements Document: Pharmakon Discovery Engine (`pde-agent-plugin`)

**Version**: 0.3.0  
**Status**: Active  
**Repository Root**: `./`

---

## 1. Product Overview

The Pharmakon Discovery Engine (`pde-agent-plugin`) is a multi-agent pre-clinical drug discovery and target evaluation plugin package. It equips autonomous and interactive agent harnesses with deterministic domain command-line tools (`bin/pde`), 43 scientific domain and workflow skills (`skills/`), 22 specialist agent role definitions (`templates/`), a 4-layer cryptographic provenance hierarchy, a 10-check mechanical validation gate, and an interactive HTML dashboard (`dashboard.html`) containing 20 scientific visualization studios.

The system supports pre-clinical discovery programs across Stages 0 through 4:

- **Stage 0 (Hypothesis Triage & Bounded Fast-Fail)**: Ingestion and evaluation of candidate therapeutic hypotheses, ELO-ranked hypothesis tournaments, citation verification, manufacturing feasibility checks, and bounded structural druggability screening.
- **Stage 1 (Target Nomination)**: Human genetic constraint and disease association evaluation, regulatory variant scoring, tissue and single-cell RNA expression profiling, structural confidence and pocket druggability analysis, and formal Stage 1 gate evaluation.
- **Stage 2 (Hit Discovery & Virtual Screening)**: Compound identity resolution, physicochemical descriptor calculation, structural alert filtering (PAINS, Brenk, aggregators), molecular docking, and high-throughput screening data analysis.
- **Stage 3 (Lead Optimization)**: Structure-activity relationship (SAR) decomposition (BRICS), matched molecular pair (MMP) and activity cliff detection, multi-parameter optimization (MPO), and rule-based ADMET endpoint classification.
- **Stage 4 (Preclinical Candidate Selection)**: Non-compartmental pharmacokinetic (NCA PK) analysis, allometric human dose projection, static drug-drug interaction (DDI) risk evaluation, repeat-dose toxicology margin calculation, and regulatory dossier compilation.

---

## 2. Problem Statement & Objectives

### 2.1 Problem Statement
Language model agents operating on biomedical research tasks without deterministic grounding are prone to three failure modes:
1. **Unverifiable Quantitative Claims**: Fabricating or misquoting numerical metrics (such as pLDDT scores, LOEUF values, IC50 measurements, or docking energies) without raw data provenance.
2. **Threshold Invention**: Applying arbitrary decision cutoffs to biological or chemical measurements rather than cited, version-controlled domain standards.
3. **Omission of Methodological Caveats**: Dropping negative findings, assay limitations, or structural caveats when summarizing technical outputs into executive reports.

### 2.2 Core Objectives
1. **Deterministic Two-Phase Execution**: Separate data acquisition/computation (Phase 1, network-enabled or compute-bound) from thresholded scientific interpretation (Phase 2, strictly offline and deterministic).
2. **Cryptographic Provenance**: Bind every Layer 0 data artifact to a `.meta.json` sidecar recording SHA-256 file digests, endpoint parameters, environment manifest hashes (`tools/ENV_VERSION`), and capability snapshots.
3. **Mechanical Verification**: Enforce a 10-check validation gate (`bin/pde validate check`) that audits file existence, SHA-256 integrity, inline JSONPath source citations, and verbatim mandatory relay codes before any specialist finding is accepted.
4. **Portable Multi-Target Packaging**: Compile a single source tree (`skills/`, `templates/`, `tools/`, `pde_plugin/`) into standard agent harness plugin targets (`.agents/plugins/pharmakon-discovery-engine/`), portable skill archives (`dist/skill-bundles/`), a Python tool bridge (`pde_plugin/tool_bridge.py`), and a Model Context Protocol (MCP) server (`pde_plugin/mcp_server.py`).

---

## 3. System Architecture

### 3.1 Repository Layout

```text
./
|-- SKILL.md
|-- README.md
|-- prd.md
|-- LICENSE
|-- pyproject.toml
|-- uv.lock
|-- dashboard.html
|-- assets/
|   |-- pde-skill-overview.png
|   '-- pde-skill-overview.svg
|-- bin/
|   |-- pde
|   |-- env.sh
|   |-- hypex
|   |-- elo
|   '-- prox
|-- pde_plugin/
|   |-- __init__.py
|   |-- tool_bridge.py
|   |-- mcp_server.py
|   |-- build_targets.py
|   '-- sync_skills_to_registry.py
|-- artifact-templates/
|   |-- executive/
|   |-- findings/
|   |-- gates/
|   '-- program-state/
|-- skills/
|   |-- pharmakon-discovery-engine/
|   |-- pde-dashboard/
|   |-- artifact-conventions/
|   |-- program-state-management/
|   |-- site-generation/
|   |-- target-genetic-evidence/
|   |-- protein-structure-confidence/
|   |-- pocket-druggability/
|   |-- compound-property-profile/
|   |-- binding-mode-analysis/
|   |-- admet-property-prediction/
|   |-- bioactivity-landscape/
|   |-- sar-series-analysis/
|   |-- in-vivo-pk-analysis/
|   |-- preclinical-safety-assessment/
|   '-- ... (43 skills total)
|-- templates/
|   |-- science-program-lead/
|   |-- research-operations-controller/
|   |-- computational-biologist/
|   |-- structural-biologist/
|   |-- computational-chemist/
|   |-- medicinal-chemist/
|   |-- admet-dmpk-scientist/
|   |-- experimental-biologist/
|   |-- preclinical-toxicologist/
|   |-- regulatory-scientist/
|   |-- scientific-reviewer/
|   |-- finding-validator/
|   '-- ... (22 agent role templates total)
|-- tools/
|   |-- env-manifest.txt
|   |-- ENV_VERSION
|   |-- requirements.lock
|   |-- pde/
|   |   |-- cli.py
|   |   |-- common.py
|   |   |-- core/
|   |   |-- commands/
|   |   '-- site_templates/
|   '-- vendor/
|       '-- hypex/
|-- examples/
|   '-- byoa/
|       |-- sample_private_compounds.json
|       |-- sample_private_assay.csv
|       |-- proprietary_cns_mpo_scorer.py
|       '-- skills/
|           '-- proprietary-cns-scorer/SKILL.md
|-- docs/
|-- .agents/
|   '-- plugins/
|       '-- pharmakon-discovery-engine/
|-- dist/
|   '-- skill-bundles/
'-- tests/
    |-- _fixture_workspace.py
    |-- test_custom_byoa.py
    |-- test_targets_compile.py
    |-- test_tool_bridge.py
    '-- test_dashboard.py
```

### 3.2 Integration Surfaces

| Surface | Entrypoint / Location | Description |
| :--- | :--- | :--- |
| Root Skill Discovery | `SKILL.md`, `skills/pharmakon-discovery-engine/SKILL.md` | Primary skill entrypoints loaded by agent harnesses to route domain requests and orchestrate work orders. |
| Agent Harness Plugin | `.agents/plugins/pharmakon-discovery-engine/` | Compiled plugin directory containing `plugin.json`, `rules/pde-scientific-integrity.md`, 22 subagent definitions (`agents/*.md`), and 43 skills (`skills/`). |
| Portable Skill Bundles | `dist/skill-bundles/*.zip` | Standalone zip archives for each skill with bundled reference documentation. |
| Python Tool Bridge | `pde_plugin/tool_bridge.py` | Typed Python functions (`ALL_PDE_TOOLS`) wrapping `bin/pde` CLI commands for direct function-calling frameworks. |
| MCP Server | `pde_plugin/mcp_server.py` | JSON-RPC 2.0 Model Context Protocol stdio server exposing all `pde_*` tools. |
| CLI Engine | `bin/pde` (`tools/pde/cli.py`) | Click-based command-line interface implementing 42 domain and operational command groups plus dynamic extension loading. |
| BYOA & Private Data Extension | `bin/pde custom` (`tools/pde/commands/custom.py`), `examples/byoa/` | Two-phase ingestion (`pde custom ingest`), proprietary algorithm execution (`pde custom run`), and offline evaluation (`pde custom analyze`) with SHA-256 data/code provenance. |

---

## 4. Functional Requirements

### 4.1 Four-Layer Artifact Hierarchy
Every PDE project workspace (default `.pde-workspace/` or initialized via `bin/pde init`) enforces a 4-layer data and documentation hierarchy:

1. **Layer 0 (`raw/<category>/`)**:
   - Primary data files fetched from external APIs or computed by local scientific binaries.
   - Every primary artifact `<stem>.<ext>` is accompanied by `<stem>.meta.json` (recording tool name, subcommand, endpoint, parameters, timestamp, `env_version`, and SHA-256 digests of all inputs and outputs).
   - Every Phase 2 analysis produces `<stem>.analysis.json` (recording the applied versioned threshold set from `tools/pde/core/thresholds.py`, computed metrics, structured categorical assessment, and `mandatory_relays`).
2. **Layer 1 (`findings/<category>/`)**:
   - Specialist Markdown reports that synthesize Layer 0 evidence for a specific work order.
   - Must include YAML frontmatter declaring `finding_id`, `work_order`, `work_order_rev`, `agent`, `role`, `layer0_sources`, and `relays_carried`.
   - Every quantitative value in prose or tables must carry an inline provenance citation (`{source: raw/<category>/<file>#$.json.path}`).
   - Every relay code emitted in any referenced `.analysis.json` must appear verbatim as `**Relay: \`<code>\`**` followed by its implication.
3. **Layer 2 (`program-state/`)**:
   - Living program records maintained exclusively by the Science Program Lead: `active-series.md`, `liability-tracker.md`, `decision-log.md`, and `open-questions.md`.
4. **Layer 4 (`executive/`, `gates/`, and `dashboard.html`)**:
   - Executive decision packages (`executive/program-summary.md`, `gates/stage1-gate-package.md`), static HTML dossiers (`site/index.html`), and the standalone interactive dashboard (`dashboard.html`).

### 4.2 Two-Phase Execution Invariant
All scientific domain commands in `bin/pde` follow a mandatory two-phase execution pattern:
- **Phase 1 (`fetch`, `search`, `run`, `compute`, `predict`, `ingest`, `resolve`, `verify`, `adopt`)**: Acquires external records or runs computational tools and writes verbatim Layer 0 files plus `.meta.json`.
- **Phase 2 (`analyze`, `analyze-prediction`, `analyze-ism`, `analyze-single-cell`, `analyze-donors`)**: Latched offline at the CLI framework level (`tools/pde/common.py`). Reads stored Layer 0 artifacts, applies named threshold sets from `tools/pde/core/thresholds.py` (with optional overrides in `.pde/thresholds.yaml`), and writes `.analysis.json`.

### 4.3 Mechanical Validation Gate (`bin/pde validate check`)
Before a specialist work order can transition from `submitted` to `mechanically_validated`, it must pass 10 automated checks:
1. `deliverables_exist`: Deliverable files exist at the declared `findings/` paths.
2. `report_headings`: Required YAML frontmatter and structured Markdown sections are present.
3. `paths_resolve`: All declared `layer0_sources` and referenced files exist under `raw/`.
4. `provenance_valid`: Valid `.meta.json` sidecars exist and SHA-256 digests match every Layer 0 file.
5. `analysis_citations`: `.analysis.json` interpretation sidecars exist and are cited.
6. `relay_coverage`: All `mandatory_relays` codes from referenced `.analysis.json` files appear verbatim (`**Relay: \`<code>\`**`).
7. `version_policy`: Environment stamp (`env_version`) consistency across sidecars.
8. `findings_integrity`: Absence of unresolved template placeholders or malformed blocks.
9. `source_tags_resolve`: All inline `{source: raw/...#$.path}` JSONPath expressions resolve against target JSON files and match numerical claims.
10. `unrecognized_json`: Absence of untracked JSON files lacking provenance sidecars in `raw/`.

### 4.4 Specialist Agent Roles (`templates/`)
The repository defines 22 agent templates, each containing `agent.yaml`, `agents.md`, and `system-prompt.md`:
- **Governance & Orchestration (5 roles)**: `science-program-lead`, `research-operations-controller`, `head-of-discovery`, `scientific-reviewer`, `finding-validator`.
- **Domain Specialists (8 roles)**: `computational-biologist`, `structural-biologist`, `computational-chemist`, `medicinal-chemist`, `admet-dmpk-scientist`, `experimental-biologist`, `preclinical-toxicologist`, `regulatory-scientist`.
- **Operations & Curation (2 roles)**: `bootstrapper`, `project-curator`.
- **Hypothesis Exploration Subsystem (7 roles)**: `hypex-supervisor`, `hypex-generation`, `hypex-reflection`, `hypex-proximity`, `hypex-tournament`, `hypex-evolution`, `hypex-meta-review`.

### 4.5 Interactive Standalone Dashboard (`dashboard.html`)
Running `bin/pde dashboard build --standalone` (or calling `pde_render_dashboard`) generates a self-contained HTML application (`dashboard.html`) with dual-mode operation (`STANDALONE SNAPSHOT` when opened as a local file, and `LIVE STREAM (SSE)` with automatic reload when served via `bin/pde dashboard serve`), light/dark SVG icon theme switching, and two synchronized panes:

1. **Left Pane — Multi-Agent Lineage & Control Plane**:
   - **Agent Forest**: Interactive SVG multi-agent lineage DAG with cursor-anchored zoom/pan, live execution status badges, work-order edges, and a collapsible Node Inspector Drawer.
   - **Node Inspector Drawer**: Displays the specialist role, work-order state, correction cycle count (`cycle / 2`), dependencies, acceptance criteria checklist, frozen **Dispatch Context Snapshot** (`.pde/control/contexts/<WO>-r<N>.json` with Layer 2 file SHA-256 hashes), and the 10-check mechanical validation matrix.
   - **Work Orders, Runs, Leases, and Event Stream Tabs**: Detailed tables of work orders (`WO-*`), specialist runs (`RUN-*`), single-flight resource leases (`af3`, `hypex-supervisor`), and an inter-agent event stream filterable by category (`Work Orders`, `Runs`, `Leases`, `Validation`).

2. **Right Pane — 20 Scientific Studios, Findings, Governance & Readiness**:
   - **3D & Structure Studios (6 studios)**:
     1. `structure`: 3Dmol.js protein structure viewer colored by per-residue pLDDT confidence.
     2. `pockets`: 3Dmol.js fpocket cavity surface and druggability score table.
     3. `docking`: 3Dmol.js receptor-ligand 3D binding pose viewer.
     4. `contacts`: Protein-ligand residue interaction distance chart and contact table.
     5. `plddt`: Plotly per-residue pLDDT confidence profile with domain boundaries.
     6. `pae`: Plotly 2D Predicted Aligned Error (PAE) heatmap.
   - **Biology, Genetics & Omics Studios (3 studios)**:
     7. `constraint`: gnomAD loss-of-function constraint (`pLI`, `LOEUF`, `mis_z`), Open Targets disease association horizontal bar chart, ClinVar pathogenicity summary, and GWAS top loci table.
     8. `expression`: Human Protein Atlas (`nTPM`) and GTEx (`TPM`) tissue expression bar chart and tau specificity index.
     9. `omics_studio`: Multi-omics studio rendering AlphaGenome in silico mutagenesis (ISM) and regulatory variant scores, single-cell dataset discovery (`cellxgene`, `scp`, `disco`), disease transcriptomics (`geo`, `disignatlas`, `spatialdb`), Allen Brain Atlas regional expression, MGI/HPO phenotype annotations, and Reactome/STRING pathways.
   - **Chemistry, ADMET, PK & Toxicology Studios (8 studios)**:
     10. `sdf`: 2D chemical structure depiction and physicochemical descriptor table.
     11. `brics`: BRICS synthetic fragment decomposition viewer.
     12. `medchem_studio`: Lipinski, Veber, QED, and SA drug-likeness scorecard, PAINS/Brenk/NIH structural alert badges, matched molecular pair (MMP) activity cliff table, multi-parameter optimization (MPO) radar, and PubChem/ChEMBL similarity hits.
     13. `admet`: Plotly multi-endpoint ADMET classification radar and parameter table.
     14. `docking_scores`: AutoDock Vina mode affinity and RMSD comparison chart.
     15. `pk_studio`: Non-compartmental PK parameter cards (`Cmax`, `AUC`, `t1/2`, `CL`, `Vdss`, `F%`), semi-log concentration-time Plotly curve, allometric human dose projection table, and FDA/EMA static DDI `R1` risk table.
     16. `bioactivity_studio`: 4PL Hill dose-response curve (`IC50`, Hill slope), HTS `Z'` assay quality badge, and off-target selectivity fold-margin table.
     17. `tox_studio`: Repeat-dose toxicology NOAEL, therapeutic index (`TI`), hERG safety margin cards, ICH S2(R1) genotoxicity battery table, and FAERS adverse event disproportionate reporting table.
   - **Clinical, Tournaments & Raw Data Studios (3 studios)**:
     18. `tournament`: Hypothesis ELO leaderboard, pairwise match history, semantic proximity clusters, evolution operator lineage tree (`ground`, `simplify`, `combine`, `oob`), and dual-use safety screen status.
     19. `competitive_studio`: ClinicalTrials.gov phase/status pipeline breakdown, patent assignee landscape, target product profile (TPP) differentiation matrix, and PubMed/preprint/citation verification records.
     20. `json`: Interactive collapsible Layer 0 JSON tree and `.meta.json` / `.analysis.json` sidecar inspector.
   - **Dossier, Governance, Stage Gate & Readiness Views**:
     - `Findings (L1)`, `Program State (L2)`, and `Executive & Gates (L4)` document viewers with inline citation highlighting.
     - `Concepts / Assessments / Decisions`: Stage 0-4 therapeutic concept cards (`concepts/`), domain assessment matrices (`assessments/`), and gate decision records (`decisions/`).
     - `Retrospectives & Readiness`: Specialist run retrospectives (`retrospectives/*.md`) and an environment readiness matrix reporting CLI binary status, Python library availability, and API credential configuration.

---

## 5. Non-Functional Requirements

1. **Offline Re-Analysis**: All Phase 2 `analyze` commands execute with network sockets blocked (`PDE_PHASE2_OFFLINE=1`) so any historical Layer 0 artifact can be re-analyzed deterministically without external API dependencies.
2. **Path Confinement & Security**: All file operations are confined to the active project workspace (`tools/pde/core/paths.py`), rejecting directory traversal (`..`) and symlink escapes, and storing only workspace-relative paths in generated artifacts and dashboard bundles.
3. **Rate Limiting & Pacing**: Outbound HTTP requests to public scientific APIs (gnomAD, UniProt, ChEMBL, PubChem, NCBI E-utilities, Europe PMC, ClinicalTrials.gov) enforce per-host QPS pacing (`tools/pde/core/qps.py`).
4. **Environment Reproducibility**: Every provenance sidecar records the SHA-256 digest of `tools/env-manifest.txt`, capturing the Python interpreter, installed package versions, and compiled binary hashes (`bin/hypex`, `bin/elo`, `bin/prox`).

---

## 6. Verification & Acceptance Criteria

The build and test suite (`tests/`) verifies:
- `tests/test_targets_compile.py`: Validates compilation of all 43 skills and 22 agent templates into `.agents/plugins/pharmakon-discovery-engine/` and `dist/skill-bundles/*.zip`.
- `tests/test_tool_bridge.py`: Validates the two-phase execution lifecycle (`pde_genetics_profile`, `pde_compound_profile`, `pde_admet_predict`), Layer 0 sidecar generation, and MCP server tool registration.
- `tests/test_dashboard.py`: Validates end-to-end generation of `dashboard.html` and `.pde-workspace/dashboard.html`, confirming all multi-agent lineage nodes, frozen context snapshots, retrospectives, environment readiness checks, Stage 0-4 concept/assessment/decision records, and all 20 scientific visualization studios render from real Layer 0-4 artifacts.
