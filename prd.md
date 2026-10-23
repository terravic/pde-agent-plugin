# Product Requirements Document: Pharmakon Discovery Engine (`PkDE` -- `pkde-agent-plugin`)

**Version**: 0.3.0  
**Status**: Active  
**Repository Root**: `./`

---

## 1. Product Overview

The Pharmakon Discovery Engine (`PkDE`, `pkde-agent-plugin`) is a multi-agent pre-clinical drug discovery and target evaluation plugin package. It equips autonomous and interactive agent harnesses with deterministic domain command-line tools (`bin/pkde`), 43 scientific domain and workflow skills (`skills/`), 22 specialist agent role definitions (`templates/`), a 4-layer cryptographic provenance hierarchy, a 10-check mechanical validation gate, and an interactive HTML dashboard (`dashboard.html`) containing 20 scientific visualization studios.

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
3. **Mechanical Verification**: Enforce a 10-check validation gate (`bin/pkde validate check`) that audits file existence, SHA-256 integrity, inline JSONPath source citations, and verbatim mandatory relay codes before any specialist finding is accepted.
4. **Portable Multi-Target Packaging**: Compile a single source tree (`skills/`, `templates/`, `tools/`, `pkde_plugin/`) into standard agent harness plugin targets (`.agents/plugins/pharmakon-discovery-engine/`), portable skill archives (`dist/skill-bundles/`), a Python tool bridge (`pkde_plugin/tool_bridge.py`), and a Model Context Protocol (MCP) server (`pkde_plugin/mcp_server.py`).

---

## 3. System Architecture

### 3.1 Repository Layout

```text
./
|-- SKILL.md
|-- README.md
|-- DESIGN.md
|-- prd.md
|-- LICENSE
|-- pyproject.toml
|-- uv.lock
|-- dashboard.html
|-- assets/
|   |-- pkde-skill-overview.png
|   '-- pkde-skill-overview.svg
|-- bin/
|   |-- pkde
|   |-- pkde-mcp
|   |-- env.sh
|   |-- hypex
|   |-- elo
|   '-- prox
|-- scripts/
|   |-- start_live_session.py
|   |-- dispatch_workorder.py
|   '-- pkde_runner.py
|-- references/
|   |-- role-skill-matrix.md
|   '-- stage0-3-playbook.md
|-- pkde_plugin/
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
|   |   |-- SKILL.md
|   |   |-- scripts/
|   |   '-- references/
|   |-- pkde-dashboard/
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
|   |-- bootstrap-preflight.sh
|   |-- install.sh
|   |-- bin/
|   |   |-- pkde
|   |   |-- hypex
|   |   |-- elo
|   |   |-- prox
|   |   '-- arch/
|   |       |-- darwin-arm64/{hypex,elo}
|   |       |-- darwin-amd64/{hypex,elo}
|   |       |-- linux-amd64/{hypex,elo}
|   |       '-- linux-arm64/{hypex,elo}
|   |-- env-manifest.txt
|   |-- ENV_VERSION
|   |-- ENV_HISTORY
|   |-- ENV_SOURCE
|   |-- manifests/
|   |-- requirements.lock
|   |-- pkde/
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
|-- .pkde-workspace/
|-- .agents/
|   |-- plugins.json
|   '-- plugins/
|       '-- pharmakon-discovery-engine/
|-- dist/
|   '-- skill-bundles/
'-- tests/
    |-- _fixture_workspace.py
    |-- test_custom_byoa.py
    |-- test_dashboard.py
    |-- test_pocket_geometric.py
    |-- test_real_execution_anti_echo.py
    |-- test_targets_compile.py
    '-- test_tool_bridge.py
```

### 3.2 Integration Surfaces

| Surface | Entrypoint / Location | Description |
| :--- | :--- | :--- |
| Root Skill Discovery | `SKILL.md`, `skills/pharmakon-discovery-engine/SKILL.md` | Primary skill entrypoints loaded by agent harnesses to route domain requests and orchestrate work orders. |
| Bundled Scripts & Playbooks | `scripts/`, `references/`, `skills/pharmakon-discovery-engine/{scripts,references}/` | Top-level and skill-local helper scripts (`start_live_session.py`, `dispatch_workorder.py`, `pkde_runner.py`) and reference matrices (`role-skill-matrix.md`, `stage0-3-playbook.md`). |
| Agent Harness Plugin | `.agents/plugins/pharmakon-discovery-engine/` | Compiled plugin directory containing `plugin.json`, `rules/pkde-scientific-integrity.md`, 22 subagent definitions (`agents/*.md`), and 43 skills (`skills/`). |
| Portable Skill Bundles | `dist/skill-bundles/*.zip` | Standalone zip archives for each skill with bundled scripts and reference documentation. |
| Python Tool Bridge | `pkde_plugin/tool_bridge.py` | Typed Python functions (`pkde_bootstrap_session`, `pkde_exec`, `pkde_dispatch_workorder`, `pkde_log_agent_message`, `pkde_validate_and_gate`, `pkde_render_dashboard`) wrapping `bin/pkde` CLI commands and control-plane workflows. |
| MCP Server | `bin/pkde-mcp`, `pkde_plugin/mcp_server.py`, `.agents/plugins/pharmakon-discovery-engine/mcp_config.json` | JSON-RPC 2.0 Model Context Protocol stdio server (`pkde-engine` / `pkde-mcp`) exposing all 6 `pkde_*` tools with explicit boolean `ToolAnnotations` (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) and a zero-dependency standard-library JSON-RPC 2.0 stdio fallback when the optional `mcp` Python package is absent. |
| CLI Engine | `bin/pkde` (`tools/pkde/cli.py`) | Click-based command-line interface implementing 42 domain and operational command groups (including `pkde workorder dispatch` and `pkde workorder validate-and-gate`) plus dynamic extension loading. |
| Multi-Architecture Native Binaries | `bin/hypex`, `bin/elo`, `tools/bin/arch/{darwin-arm64,darwin-amd64,linux-amd64,linux-arm64}/` | POSIX runtime OS/CPU dispatchers backed by pre-compiled static binaries (`CGO_ENABLED=0`) for macOS ARM64, macOS x86_64, Linux x86_64, and Linux ARM64. |
| Environment Provisioner | `tools/bootstrap-preflight.sh`, `tools/install.sh`, `bin/env.sh` | Cross-platform host prerequisite checker and hermetic provisioner for `.venv`, `[science]` dependencies, `bin/hypex`, `bin/elo`, `bin/prox`, and `tools/ENV_VERSION` stamping on Linux and macOS. |
| BYOA & Private Data Extension | `bin/pkde custom` (`tools/pkde/commands/custom.py`), `examples/byoa/` | Two-phase ingestion (`pkde custom ingest`), proprietary algorithm execution (`pkde custom run`), and offline evaluation (`pkde custom analyze`) with SHA-256 data/code provenance. |

---

## 4. Functional Requirements

### 4.1 Four-Layer Artifact Hierarchy
Every PkDE project workspace (default `.pkde-workspace/` or initialized via `bin/pkde init`) enforces a 4-layer data and documentation hierarchy:

1. **Layer 0 (`raw/<category>/`)**:
   - Primary data files fetched from external APIs or computed by local scientific binaries and built-in computational engines.
   - Every primary artifact `<stem>.<ext>` is accompanied by `<stem>.meta.json` (recording tool name, subcommand, endpoint, parameters, timestamp, `env_version`, and SHA-256 digests of all inputs and outputs).
   - Every Phase 2 analysis produces `<stem>.analysis.json` (recording the applied versioned threshold set from `tools/pkde/core/thresholds.py`, computed metrics, structured categorical assessment, and `mandatory_relays`).
2. **Layer 1 (`findings/<category>/`)**:
   - Specialist Markdown reports that synthesize Layer 0 evidence for a specific work order.
   - Must include YAML frontmatter declaring `finding_id`, `work_order`, `work_order_rev`, `agent`, `role`, `layer0_sources`, and `relays_carried`.
   - Every quantitative value in prose or tables must carry an inline provenance citation (`{source: raw/<category>/<file>#$.json.path}`).
   - Every relay code emitted in any referenced `.analysis.json` must appear verbatim as `**Relay: \`<code>\`**` followed by its implication.
3. **Layer 2 (`program-state/`)**:
   - Living program records maintained exclusively by the Science Program Lead: `active-series.md`, `liability-tracker.md`, `decision-log.md`, and `open-questions.md`.
4. **Layer 4 (`executive/`, `gates/`, and `dashboard.html`)**:
   - Executive decision packages (`executive/program-summary.md`, `gates/stage1-gate-package.md`), static HTML dossiers (`site/index.html`), and the standalone interactive dashboard (`dashboard.html`).

### 4.2 Two-Phase Execution Invariant & Built-In Pocket Detection Fallback
All scientific domain commands in `bin/pkde` follow a mandatory two-phase execution pattern:
- **Phase 1 (`fetch`, `search`, `run`, `compute`, `predict`, `ingest`, `resolve`, `verify`, `adopt`)**: Acquires external records or runs computational tools and writes verbatim Layer 0 files plus `.meta.json`.
- **Phase 2 (`analyze`, `analyze-prediction`, `analyze-ism`, `analyze-single-cell`, `analyze-donors`)**: Latched offline at the CLI framework level (`tools/pkde/common.py`). Reads stored Layer 0 artifacts, applies named threshold sets from `tools/pkde/core/thresholds.py` (with optional overrides in `.pkde/thresholds.yaml`), and writes `.analysis.json`.
- **Built-In Geometric Pocket Detection (`bin/pkde pocket run --backend [auto|fpocket|geometric]`)**:
  - When `--backend auto` (default) is used, `pkde pocket run` invokes the external `fpocket` binary if present on `PATH`, and automatically falls back to a built-in Python/NumPy 3D lattice protein-solvent-protein (PSP) enclosure and alpha-probe cavity detector (`tools/pkde/commands/pocket.py`) when `fpocket` is unavailable. If `numpy` or `gemmi` is absent on the host, the geometric pocket detector and structure parser automatically fall back to pure-Python implementations (`_run_geometric_pocket_detector_pure_python`, `_parse_atoms_fallback`).
  - The `geometric` backend parses PDB (`.pdb`, `.ent`) and mmCIF (`.cif`, `.mmcif`) structures, clusters buried and cleft cavities via 26-connected breadth-first search, computes volume, residue hydrophobicity, and calibrated druggability scores, and writes a complete `<stem>_fpocket/` output tree (`<stem>_info.txt` and `pockets/pocket{rank}_atm.{pdb,cif}`) compatible with `pkde pocket analyze`, `pkde docking prepare`, `pkde structure annotate-topology`, and the 3Dmol.js dashboard viewer.
  - Whenever the `geometric` backend executes, `pkde pocket run` emits the mandatory relay `pocket.geometric_fallback_backend` in `.pockets.meta.json` (propagated by `pkde pocket analyze` into `.pocket.analysis.json`), and `pkde doctor` classifies missing `fpocket` as a non-blocking `CAVEAT`.

### 4.3 Mechanical Validation Gate (`bin/pkde validate check` & `bin/pkde workorder validate-and-gate`)
Building on the 4-layer hierarchy, before a specialist work order can transition from `submitted` to `mechanically_validated`, it must pass 10 automated checks:
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

### 4.5 Interactive Standalone Dashboard (`dashboard.html`), Theme Specifications & Cross-Platform Failover Rendering
Running `bin/pkde dashboard build --standalone` (or calling `pkde_render_dashboard`) generates a self-contained HTML application (`dashboard.html`) governed by `DESIGN.md` with dual-mode operation (`STANDALONE SNAPSHOT` when opened as a local file, and `LIVE STREAM (SSE)` with automatic reload when served via `bin/pkde dashboard serve`), Light / Dark / System theme switching, cross-platform 3D/2D rendering failover, and two synchronized panes:

1. **Theme Selector, Cross-Platform OS Detection & Data Visualization Color Palette Specifications (`DESIGN.md`)**:
   - **Three-Icon Light / Dark / System Selector (`#theme-selector`)**: Segmented control in the top navigation bar containing three side-by-side SVG icon buttons (`#theme-btn-light` with a sun SVG icon, `#theme-btn-dark` with a crescent moon SVG icon, and `#theme-btn-system` with a computer monitor SVG icon). The selected mode (`light`, `dark`, or `system`) is highlighted via the `active` class (`aria-pressed="true"`) and persisted in `localStorage` (`pkde-theme-mode`).
   - **Cross-Platform System Theme Detection (`macOS`, `Linux`, `Windows`)**:
     - **Browser / Webview Layer (`resolveSystemTheme`)**: Queries `window.matchMedia('(prefers-color-scheme: dark)')` and registers a `'change'` listener so operating system appearance changes apply in real time when `system` mode is active.
     - **Host OS Layer (`_detect_host_system_theme` in `tools/pkde/commands/dashboard.py`)**: Queries the host operating system preference (`defaults read -g AppleInterfaceStyle` on macOS, `winreg` `AppsUseLightTheme` on Windows, and `GTK_THEME` / `gsettings` / `kdeglobals` on Linux) and embeds `os_platform` and `system_theme` in `bundle["agent_system"]["environment"]` as a fallback for headless or restricted webviews.
   - **Light Mode Tokens**: Background `#FAFAF9`, Cards & Surfaces `#FFFFFF`, Borders `#E7E5E4`, Text Primary `#1C1917`, Text Secondary `#787774`.
   - **Dark Mode Tokens**: Background `#0D0E11`, Cards & Surfaces `#16171D`, Borders `#292A30`, Text Primary `#ECE8E2`, Text Secondary `#9A9895`.
   - **Semantic Data Visualization Palette**: Teal `#0D9488` (primary series and structural bonds), Amber `#D97706` (secondary series and warnings), Indigo `#4F46E5` (comparison series and molecular groups), Emerald `#059669` (positive/passing metrics), Rose `#E11D48` (negative trends and critical highlights).

2. **Cross-Platform 3D & 2D Failover Rendering Engine**:
   - **3D Molecular Failover (`canUseWebGL` + `renderSoftware3DMoleculeFallback`)**: Automatically detects whether hardware-accelerated WebGL (`3Dmol.js`) is available. In headless or embedded Linux webviews where WebGL is unavailable or external CDN scripts are restricted by Content Security Policy, the 3D studios (`structure`, `pockets`, `docking`, `sdf`) automatically switch to a built-in interactive software 3D projection engine that parses mmCIF, PDB, PDBQT, and SDF payloads, infers covalent and C-alpha backbone traces, and supports drag-to-rotate, scroll-to-zoom, residue/atom hover coordinate inspection, and `Cartoon` / `Stick` / `Sphere` style switching. Users can also manually toggle between `Auto` and `Software 3D` via the studio toolbar.
   - **2D Chart Failover (`renderPlotWithFallback` + `renderSvgChartFallback`)**: Automatically uses `Plotly.js` when available and falls back to an inline SVG chart renderer supporting bar charts, line/scatter profiles, radar plots, and 2D heatmaps when offline or under restricted CSP.

3. **Left Pane -- Multi-Agent Lineage & Control Plane**:
   - **Agent Forest**: Interactive SVG multi-agent lineage DAG with cursor-anchored zoom/pan, live execution status badges, work-order edges, and a collapsible Node Inspector Drawer.
   - **Node Inspector Drawer**: Displays the specialist role, work-order state, correction cycle count (`cycle / 2`), dependencies, acceptance criteria checklist, frozen **Dispatch Context Snapshot** (`.pkde/control/contexts/<WO>-r<N>.json` with Layer 2 file SHA-256 hashes), and the 10-check mechanical validation matrix.
   - **Work Orders, Runs, Leases, and Event Stream Tabs**: Detailed tables of work orders (`WO-*`), specialist runs (`RUN-*`), single-flight resource leases (`af3`, `hypex-supervisor`), and an inter-agent event stream filterable by category (`Work Orders`, `Runs`, `Leases`, `Validation`).

4. **Right Pane -- 20 Scientific Studios, Findings, Governance & Readiness**:
   - **3D & Structure Studios (6 studios)**:
     1. `structure`: 3Dmol.js / Software 3D protein structure viewer colored by per-residue pLDDT confidence.
     2. `pockets`: 3Dmol.js / Software 3D fpocket/geometric cavity surface and druggability score table.
     3. `docking`: 3Dmol.js / Software 3D receptor-ligand 3D binding pose viewer.
     4. `contacts`: Protein-ligand residue interaction distance chart and contact table.
     5. `plddt`: Plotly / SVG per-residue pLDDT confidence profile with domain boundaries.
     6. `pae`: Plotly / SVG 2D Predicted Aligned Error (PAE) heatmap.
   - **Biology, Genetics & Omics Studios (3 studios)**:
     7. `constraint`: gnomAD loss-of-function constraint (`pLI`, `LOEUF`, `mis_z`), Open Targets disease association horizontal bar chart, ClinVar pathogenicity summary, and GWAS top loci table.
     8. `expression`: Human Protein Atlas (`nTPM`) and GTEx (`TPM`) tissue expression bar chart and tau specificity index.
     9. `omics_studio`: Multi-omics studio rendering AlphaGenome in silico mutagenesis (ISM) and regulatory variant scores, single-cell dataset discovery (`cellxgene`, `scp`, `disco`), disease transcriptomics (`geo`, `disignatlas`, `spatialdb`), Allen Brain Atlas regional expression, MGI/HPO phenotype annotations, and Reactome/STRING pathways.
   - **Chemistry, ADMET, PK & Toxicology Studios (8 studios)**:
     10. `sdf`: 3D conformer viewer (3Dmol.js / Software 3D), 2D chemical structure depiction, and physicochemical descriptor table.
     11. `brics`: BRICS synthetic fragment decomposition viewer.
     12. `medchem_studio`: Lipinski, Veber, QED, and SA drug-likeness scorecard, PAINS/Brenk/NIH structural alert badges, matched molecular pair (MMP) activity cliff table, multi-parameter optimization (MPO) radar, and PubChem/ChEMBL similarity hits.
     13. `admet`: Plotly / SVG multi-endpoint ADMET classification radar and parameter table.
     14. `docking_scores`: AutoDock Vina mode affinity and RMSD comparison chart.
     15. `pk_studio`: Non-compartmental PK parameter cards (`Cmax`, `AUC`, `t1/2`, `CL`, `Vdss`, `F%`), semi-log concentration-time curve, allometric human dose projection table, and FDA/EMA static DDI `R1` risk table.
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

### 4.6 Model Context Protocol (MCP) Server & Tool Annotations (`pkde_plugin/mcp_server.py`)
The stdio MCP server (`pkde-engine`, registered via `.agents/plugins/pharmakon-discovery-engine/mcp_config.json`, `./bin/pkde-mcp`, and the `pkde-mcp` console entrypoint) exposes 6 orchestration and execution tools backed by `pkde_plugin/tool_bridge.py`. If the optional `mcp` Python package (`FastMCP`) is not installed on the host, `pkde_plugin/mcp_server.py` automatically falls back to a built-in Python standard-library JSON-RPC 2.0 stdio server (`_run_stdlib_stdio_server`). Every tool declares explicit boolean values (`true` / `false`) for all four MCP `ToolAnnotations` hints (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`):

| MCP Tool Name | Handler Behavior | `readOnlyHint` | `destructiveHint` | `idempotentHint` | `openWorldHint` |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `pkde_bootstrap_session` | Initializes `.pkde/program.yaml` from the user prompt, logs `prompt.received`, builds `dashboard.html`, and starts/verifies the non-blocking HTTP+SSE dashboard server on `0.0.0.0:8765`. | `false` | `false` | `false` | `false` |
| `pkde_exec` | Executes any two-phase or control-plane `pkde` CLI subcommand (`python -m pkde.cli ...`) and refreshes `dashboard.html`. | `false` | `true` | `false` | `true` |
| `pkde_dispatch_workorder` | Executes the 4-step Work Order intake ceremony (writes spec YAML, creates/commits `WO-###`, freezes context snapshot, acquires resource lease, starts `RUN-###`, and returns `specialist_brief`). | `false` | `false` | `false` | `false` |
| `pkde_log_agent_message` | Appends an inter-agent communication event (`agent.message`) to `.pkde/control/events.ndjson` and refreshes `dashboard.html`. | `false` | `false` | `false` | `false` |
| `pkde_validate_and_gate` | Runs the 10-check mechanical validation gate (`pkde validate check`) and routes to `PASSED` (releases leases), `CORRECTION_REQUIRED` (up to 2 retry cycles), or `DATA_INTEGRITY_FAILURE` (immediate halt). | `false` | `false` | `false` | `false` |
| `pkde_render_dashboard` | Deterministically renders the standalone interactive `dashboard.html` from local workspace state without appending control events or calling external APIs. | `false` | `false` | `true` | `false` |

---

## 5. Non-Functional Requirements

1. **Offline Re-Analysis**: All Phase 2 `analyze` commands execute with network sockets blocked (`PKDE_PHASE2_OFFLINE=1`) so any historical Layer 0 artifact can be re-analyzed deterministically without external API dependencies.
2. **Preflight Readiness, Non-Blocking Missing-Library Handling & Degraded Offline Detection**: `bin/pkde doctor` probes local toolchain integrity and external scientific API reachability (`_check_external_scientific_apis` with a bounded `1.5s` socket timeout and `PKDE_OFFLINE=1` short-circuit), returning `execution_mode` (`"full"` | `"degraded_offline"` | `"blocked"`). Cross-platform environment manifest drift (`env-version`) and missing optional scientific libraries (`rdkit`, `gemmi`, `biopython`, `scipy`, `pubchempy`, `requests`, `jsonpath_ng`, `zstandard`) report as non-blocking `WARN` checks rather than `FAIL` so unaffected domain commands remain operational. When `requests` is absent, `tools/pkde/core/http.py` automatically falls back to Python standard-library `urllib.request`.
3. **Hermetic Python & Sandbox-Safe File I/O**: `bin/env.sh`, `bin/pkde`, `bin/pkde-mcp`, `bin/prox`, and `pkde_plugin/tool_bridge.py` prefer `$PKDE_ROOT/.venv/bin/python`, set `PYTHONNOUSERSITE=1`, and isolate `PYTHONPATH` (`$PKDE_ROOT:$PKDE_ROOT/tools:$PKDE_ROOT/tools/vendor/hypex`) from host site-packages. Dashboard HTML generation (`_safe_write_html` in `tools/pkde/commands/dashboard.py`) falls back from `os.replace()` to direct writes with guaranteed temporary file cleanup in `finally:` blocks when running inside sandboxes that restrict atomic file replacement.
4. **Path Confinement & Security**: All file operations are confined to the active project workspace (`tools/pkde/core/paths.py`), rejecting directory traversal (`..`) and symlink escapes, and storing only workspace-relative paths in generated artifacts and dashboard bundles.
5. **Rate Limiting & Pacing**: Outbound HTTP requests to public scientific APIs (gnomAD, UniProt, ChEMBL, PubChem, NCBI E-utilities, Europe PMC, ClinicalTrials.gov) enforce per-host QPS pacing (`tools/pkde/core/qps.py`).
6. **Environment Reproducibility & Multi-Architecture Binaries**: Every provenance sidecar records the SHA-256 digest of `tools/env-manifest.txt`, capturing the Python interpreter, installed package versions, wrapper scripts (`bin/pkde`, `bin/hypex`, `bin/elo`, `bin/prox`), and all 8 cross-compiled static native binaries (`tools/bin/arch/{darwin-arm64,darwin-amd64,linux-amd64,linux-arm64}/{hypex,elo}` built with `CGO_ENABLED=0 -trimpath`).

---

## 6. Verification & Acceptance Criteria

The build and test suite (`tests/`, 37 tests across 6 test modules) verifies:
- `tests/test_custom_byoa.py` (4 tests): Validates two-phase private CSV ingestion (`pkde custom ingest`), proprietary Python algorithm execution (`pkde custom run`), offline evaluation (`pkde custom analyze`), relay attribution (`pkde relays`), and dynamic Click extension loading.
- `tests/test_pocket_geometric.py` (3 tests): Validates the built-in Python/NumPy geometric pocket detector (`pkde pocket run --backend [geometric|auto]`) and offline `pkde pocket analyze` (global and `--near`) across PDB and mmCIF structures, `pocket.geometric_fallback_backend` relay propagation, and `pkde docking prepare` grid-box compatibility.
- `tests/test_targets_compile.py` (5 tests): Validates compilation of all 43 skills and 22 agent templates into `.agents/plugins/pharmakon-discovery-engine/` and `dist/skill-bundles/*.zip`, verifies parity between root `scripts/` and `references/` and `skills/pharmakon-discovery-engine/{scripts,references}/`, confirms every `scripts/...` and `references/...` path cited in `SKILL.md` resolves across root, skill-local, and compiled plugin locations, and verifies multi-architecture (`darwin-arm64`, `darwin-amd64`, `linux-amd64`, `linux-arm64`) binary headers and wrapper dispatch.
- `tests/test_tool_bridge.py` (10 tests): Validates `pkde_exec` CLI execution, `pkde_dispatch_workorder` and native `./bin/pkde workorder dispatch` 4-step intake and single-flight resource lease locking, `pkde_validate_and_gate` and `./bin/pkde workorder validate-and-gate` 10-check validation gate, hermetic `PYTHONPATH` isolation against incompatible host site-packages, `pkde doctor` `execution_mode` (`full` vs. `degraded_offline`), cross-platform environment drift and missing-library non-blocking behavior, stdlib MCP server fallback when `mcp` is missing, and `pkde-engine` MCP server exposure of all 6 tools with explicit boolean `ToolAnnotations`.
- `tests/test_dashboard.py` (10 tests): Validates end-to-end generation of `dashboard.html` and `.pkde-workspace/dashboard.html`, sandbox-safe HTML fallback writing (`_safe_write_html`) when `os.replace` raises `PermissionError` or `OSError`, multi-agent lineage nodes, frozen context snapshots, retrospectives, environment readiness checks (`bootstrap_ready`), cross-platform host OS theme detection (`_detect_host_system_theme` across macOS, Linux, and Windows), the three-icon Light / Dark / System theme selector (`#theme-selector`), cross-platform 3D (`canUseWebGL`, `renderSoftware3DMoleculeFallback`) and 2D (`renderPlotWithFallback`, `renderSvgChartFallback`) failover renderers, Stage 0-4 concept/assessment/decision records, theme and color palette tokens, and all 20 scientific visualization studios.
- `tests/test_real_execution_anti_echo.py` (5 tests): Differential and mutation-verification suite proving that domain engines compute real mathematical results from inputs rather than returning static/echoed passes: (1) RDKit descriptor calculation and Lipinski rule evaluation on Aspirin (`MW = 180.16`, `0` violations) vs. a heavy lipopeptide (`MW = 697.96`, `2` violations); (2) non-compartmental PK trapezoidal integration proving exact $2.0\times$ scaling of $\text{C}_{\max}$, $\text{AUC}_{0\text{-}t}$, and $\text{AUC}_{0\text{-}\infty}$ with invariant $t_{1/2} = 1.0\text{ h}$ and $\lambda_z = \ln(2)$; (3) 3D geometric pocket detection positive control (spherical cavity, `n_pockets >= 1`) vs. negative control (1D linear chain, `n_pockets == 0`); (4) end-to-end execution of native `bin/hypex`, `bin/elo`, and `bin/prox` binaries across opposite tournament outcomes (`1520` vs. `1480` Elo) and TF-IDF cosine similarity clustering; and (5) 1-byte Layer 0 SHA-256 tamper detection (`unrecognized_json` and `source_tags_resolve` `DATA_INTEGRITY` failure).


