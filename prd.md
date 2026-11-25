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
|-- SECURITY_AUDIT.md
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
|   '-- legal/                                     # Draft policy templates (privacy, terms, refunds, cookies)
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
    |-- test_multi_agent_cohort_and_no_stubs.py
    |-- test_pocket_geometric.py
    |-- test_real_execution_anti_echo.py
    |-- test_security_and_a11y.py
    |-- test_skill_contract.py
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
| Python Tool Bridge | `pkde_plugin/tool_bridge.py` | Typed Python functions (`pkde_bootstrap_session`, `pkde_exec`, `pkde_dispatch_workorder`, `pkde_dispatch_cohort`, `pkde_manage_cohort`, `pkde_log_agent_message`, `pkde_validate_and_gate`, `pkde_render_dashboard`) wrapping `bin/pkde` CLI commands and control-plane workflows. |
| MCP Server | `bin/pkde-mcp`, `pkde_plugin/mcp_server.py`, `.agents/plugins/pharmakon-discovery-engine/mcp_config.json` | JSON-RPC 2.0 Model Context Protocol stdio server (`pkde-engine` / `pkde-mcp`) exposing all 8 `pkde_*` tools with explicit boolean `ToolAnnotations` (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) and a strict-schema standard-library JSON-RPC 2.0 stdio fallback when the optional `mcp` Python package is absent. |
| CLI Engine | `bin/pkde` (`tools/pkde/cli.py`) | Click-based command-line interface implementing 42 domain and operational command groups (including `pkde workorder dispatch`, `dispatch-cohort`, `advance-wave`, `bind-subagent`, `renew-lease`, and `validate-and-gate`) plus dynamic extension loading. |
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
  - The `geometric` backend parses PDB (`.pdb`, `.ent`) and mmCIF (`.cif`, `.mmcif`) structures, clusters buried and cleft cavities via 26-connected breadth-first search, computes volume, residue hydrophobicity, and calibrated druggability scores, and writes a complete `<stem>_fpocket/` output tree (`<stem>_info.txt` and `pockets/pocket{rank}_atm.{pdb,cif}`) compatible with `pkde pocket analyze`, `pkde docking prepare`, `pkde structure annotate-topology`, and the offline 3D dashboard viewer.
  - Whenever the `geometric` backend executes, `pkde pocket run` emits the mandatory relay `pocket.geometric_fallback_backend` in `.pockets.meta.json` (propagated by `pkde pocket analyze` into `.pocket.analysis.json`), and `pkde doctor` classifies missing `fpocket` as a non-blocking `CAVEAT`.

### 4.3 Mechanical Validation Gate & Multi-Agent Work-Order Orchestration (`bin/pkde validate check` & `bin/pkde workorder`)
Building on the 4-layer hierarchy, the control plane enforces strict work-order specification contracts, multi-wave cohort scheduling, single-flight resource leases, and a 10-check mechanical validation gate:

1. **Work-Order Specification Contract (`pkde workorder create` & `pkde_dispatch_workorder`)**:
   - Validates `requested_role` against the 22 canonical agent roles (`PKDE_AGENT_ROLES` in `tools/pkde/commands/workorder.py`), rejecting unknown or misspelled personas.
   - Requires a non-empty `decision_question`, a non-empty `deliverables.layer_1` list of relative paths under `findings/`, and either a non-empty `deliverables.layer_0_classes` list or `deliverables.synthesis_only: true`.
2. **Multi-Persona Cohort Dispatch & Dependency Waves (`pkde workorder dispatch-cohort`, `advance-wave`, `bind-subagent`)**:
   - Accepts a multi-persona cohort specification (`COHORT-###`) with symbolic keys and `depends_on` edges, validates the dependency DAG for unknown references and cycles, creates and commits all work orders, starts Wave 1 (`depends_on: []`) specialist runs immediately, and queues dependent waves (`status: "queued_on_dependencies"`).
   - Emits concrete `subagent_invocations` arrays (`TypeName`, `Role`, `Prompt`, `Model`, `Workspace`) and binds returned subagent `conversation_id` values to `.pkde/control/work-orders/<WO>.json` and `.pkde/control/runs/<RUN>.json` (matching by `work_order_id`, `run_id`, or `role`, and reporting any unmatched entries).
   - Automatically promotes queued Wave 2+ work orders when upstream dependencies pass `pkde_validate_and_gate`.
3. **Single-Flight Resource Leases with TTL Expiry (`af3`, `hypex-supervisor`)**:
   - Every resource lease records `acquired_at`, `ttl_seconds` (default `3600` seconds), and `expires_at` in `.pkde/control/leases/<resource>.json`.
   - Expired leases are automatically released (`lease.expired` event logged to `.pkde/control/events.ndjson`) on subsequent acquisition attempts, and active runs can extend their lease via `pkde workorder renew-lease`.
4. **Ten-Check Mechanical Validation Gate (`bin/pkde validate check` & `bin/pkde workorder validate-and-gate`)**:
   - Before a specialist work order can transition from `submitted` to `mechanically_validated`, it must pass a non-overridable `deliverables_schema` pre-check and 10 automated checks:
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
   - All control-plane state transitions (`complete`, `validate-pass`, `validate-fail`, `revise`) check the CLI return code and report explicit `TRANSITION_FAILED`, `VALIDATOR_ERROR`, or `ALREADY_VALIDATED` actions on invalid transitions.

### 4.4 Specialist Agent Roles (`templates/`)
The repository defines 22 agent templates, each containing `agent.yaml`, `agents.md`, and `system-prompt.md`:
- **Governance & Orchestration (5 roles)**: `science-program-lead`, `research-operations-controller`, `head-of-discovery`, `scientific-reviewer`, `finding-validator`.
- **Domain Specialists (8 roles)**: `computational-biologist`, `structural-biologist`, `computational-chemist`, `medicinal-chemist`, `admet-dmpk-scientist`, `experimental-biologist`, `preclinical-toxicologist`, `regulatory-scientist`.
- **Operations & Curation (2 roles)**: `bootstrapper`, `project-curator`.
- **Hypothesis Exploration Subsystem (7 roles)**: `hypex-supervisor`, `hypex-generation`, `hypex-reflection`, `hypex-proximity`, `hypex-tournament`, `hypex-evolution`, `hypex-meta-review`.

### 4.5 Interactive Standalone Dashboard (`dashboard.html`), Theme Specifications & Zero-CDN Offline Rendering
Running `bin/pkde dashboard build --standalone` (or calling `pkde_render_dashboard`) generates a self-contained HTML application (`dashboard.html`) governed by `DESIGN.md` with dual-mode operation (`STANDALONE SNAPSHOT` when opened as a local file, and `LIVE STREAM (SSE)` when served via `bin/pkde dashboard serve`), strict Content-Security-Policy, zero external CDN/font requests, WCAG 2.2 AA contrast and keyboard navigation, Light / Dark / System theme switching, and two synchronized panes:

1. **Theme Selector, Cross-Platform OS Detection & Data Visualization Color Palette Specifications (`DESIGN.md`)**:
   - **Three-Icon Light / Dark / System Selector (`#theme-selector`)**: Segmented control in the top navigation bar containing three side-by-side SVG icon buttons (`#theme-btn-light`, `#theme-btn-dark`, and `#theme-btn-system`). The selected mode (`light`, `dark`, or `system`) is highlighted via the `active` class (`aria-pressed="true"`) and persisted in `localStorage` (`pkde-theme-mode`).
   - **Cross-Platform System Theme Detection (`macOS`, `Linux`, `Windows`)**:
     - **Browser / Webview Layer (`resolveSystemTheme`)**: Queries `window.matchMedia('(prefers-color-scheme: dark)')` and registers a `'change'` listener so operating system appearance changes apply in real time when `system` mode is active.
     - **Host OS Layer (`_detect_host_system_theme` in `tools/pkde/commands/dashboard.py`)**: Queries the host operating system preference (`defaults read -g AppleInterfaceStyle` on macOS, `winreg` `AppsUseLightTheme` on Windows, and `GTK_THEME` / `gsettings` / `kdeglobals` on Linux) and embeds `os_platform` and `system_theme` in `bundle["agent_system"]["environment"]` as a fallback for headless or restricted webviews.
   - **Light Mode Tokens (WCAG 2.2 AA >= 4.5:1)**: Background `#FAFAF9`, Cards & Surfaces `#FFFFFF`, Borders `#E7E5E4`, Text Primary `#1C1917`, Text Secondary `#575653`, Warning Alert `#B45309`.
   - **Dark Mode Tokens (WCAG 2.2 AA >= 4.5:1)**: Background `#0D0E11`, Cards & Surfaces `#16171D`, Borders `#292A30`, Text Primary `#ECE8E2`, Text Secondary `#9A9895`.
   - **Semantic Data Visualization Palette**: Teal `#0D9488` (primary series and structural bonds), Amber `#D97706` (secondary series and warnings), Indigo `#4F46E5` (comparison series and molecular groups), Emerald `#059669` (positive/passing metrics), Rose `#E11D48` (negative trends and critical highlights).

2. **Zero-CDN Offline 3D & 2D Rendering Engine**:
   - **3D Molecular Engine (`canUseWebGL` + `renderSoftware3DMoleculeFallback`)**: Renders mmCIF, PDB, PDBQT, and SDF payloads locally without loading external CDN scripts, supporting drag-to-rotate, scroll-to-zoom, residue/atom hover coordinate inspection, and `Cartoon` / `Stick` / `Sphere` styles.
   - **2D Chart Engine (`renderPlotWithFallback` + `renderSvgChartFallback`)**: Renders bar charts, line/scatter profiles, radar plots, and 2D heatmaps via an inline SVG chart engine with zero outbound requests.

3. **Left Pane -- Multi-Agent Lineage & Control Plane**:
   - **Agent Forest**: Interactive SVG multi-agent lineage DAG with cursor-anchored zoom/pan, keyboard focusable nodes, explicit textual status tags, work-order edges, and a collapsible Node Inspector Drawer.
   - **Node Inspector Drawer**: Displays the specialist role, work-order state, correction cycle count (`cycle / 2`), dependencies, acceptance criteria checklist, frozen **Dispatch Context Snapshot** (`.pkde/control/contexts/<WO>-r<N>.json` with Layer 2 file SHA-256 hashes), and the 10-check mechanical validation matrix.
   - **Work Orders, Runs, Leases, and Event Stream Tabs**: Detailed tables of work orders (`WO-*`), specialist runs (`RUN-*`), single-flight resource leases (`af3`, `hypex-supervisor`), and an inter-agent event stream filterable by category (`Work Orders`, `Runs`, `Leases`, `Validation`).

4. **Right Pane -- 20 Scientific Studios, Findings, Governance & Readiness**:
   - **3D & Structure Studios (6 studios)**: `structure`, `pockets`, `docking`, `contacts`, `plddt`, `pae`.
   - **Biology, Genetics & Omics Studios (3 studios)**: `constraint`, `expression`, `omics_studio`.
   - **Chemistry, ADMET, PK & Toxicology Studios (8 studios)**: `sdf`, `brics`, `medchem_studio`, `admet`, `docking_scores`, `pk_studio`, `bioactivity_studio`, `tox_studio`.
   - **Clinical, Tournaments & Raw Data Studios (3 studios)**: `tournament`, `competitive_studio`, `json`.
   - **Dossier, Governance, Stage Gate & Readiness Views**: `Findings (L1)`, `Program State (L2)`, `Executive & Gates (L4)`, `Concepts / Assessments / Decisions`, and `Retrospectives & Readiness`.

### 4.6 Model Context Protocol (MCP) Server & Tool Annotations (`pkde_plugin/mcp_server.py`)
The stdio MCP server (`pkde-engine`, registered via `.agents/plugins/pharmakon-discovery-engine/mcp_config.json`, `./bin/pkde-mcp`, and the `pkde-mcp` console entrypoint) exposes 8 orchestration and execution tools backed by `pkde_plugin/tool_bridge.py`. If the optional `mcp` Python package (`FastMCP`) is not installed on the host, `pkde_plugin/mcp_server.py` automatically falls back to a built-in Python standard-library JSON-RPC 2.0 stdio server with strict argument schema validation (rejecting unknown keys, missing required parameters, and mismatched JSON types with `-32602`). Every tool declares explicit boolean values (`true` / `false`) for all four MCP `ToolAnnotations` hints (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`):

| MCP Tool Name | Handler Behavior | `readOnlyHint` | `destructiveHint` | `idempotentHint` | `openWorldHint` |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `pkde_bootstrap_session` | Initializes `.pkde/program.yaml` from the user prompt, logs `prompt.received`, builds `dashboard.html`, and starts/verifies the non-blocking HTTP+SSE dashboard server on `127.0.0.1:8765` (overridable via `host` or `PKDE_DASHBOARD_HOST`). | `false` | `false` | `false` | `false` |
| `pkde_exec` | Executes any two-phase or control-plane `pkde` CLI subcommand (`python -m pkde.cli ...`) and refreshes `dashboard.html`. | `false` | `true` | `false` | `true` |
| `pkde_dispatch_workorder` | Executes the 4-step Work Order intake ceremony (writes spec YAML, creates/commits `WO-###`, freezes context snapshot, acquires resource lease with TTL, starts `RUN-###`, and returns `specialist_brief` and `subagent_invocation`). | `false` | `false` | `false` | `false` |
| `pkde_dispatch_cohort` | Dispatches a multi-persona cohort (`COHORT-###`) across up to 22 specialist personas with DAG dependency waves (`depends_on`), starts Wave 1 runs immediately, queues Wave 2+ runs, and returns `subagent_invocations`. | `false` | `false` | `false` | `false` |
| `pkde_manage_cohort` | Manages an active multi-agent cohort (`status`, `bind_subagent`, `advance_wave`, `validate_cohort`, `renew_lease`). | `false` | `false` | `false` | `false` |
| `pkde_log_agent_message` | Appends an inter-agent communication event (`agent.message`) to `.pkde/control/events.ndjson` and refreshes `dashboard.html`. | `false` | `false` | `false` | `false` |
| `pkde_validate_and_gate` | Runs the 10-check mechanical validation gate (`pkde validate check`), routes to `PASSED` (releases leases and promotes ready Wave 2+ cohort dependents), `CORRECTION_REQUIRED` (up to 2 retry cycles), or `DATA_INTEGRITY_FAILURE`, and verifies state transitions. | `false` | `false` | `false` | `false` |
| `pkde_render_dashboard` | Deterministically renders the standalone interactive `dashboard.html` from local workspace state without appending control events or calling external APIs. | `false` | `false` | `true` | `false` |

---

## 5. Non-Functional Requirements

1. **Offline Re-Analysis**: All Phase 2 `analyze` commands execute with network sockets blocked (`PKDE_PHASE2_OFFLINE=1`) so any historical Layer 0 artifact can be re-analyzed deterministically without external API dependencies.
2. **Preflight Readiness, Non-Blocking Missing-Library Handling & Degraded Offline Detection**: `bin/pkde doctor` probes local toolchain integrity and external scientific API reachability (`_check_external_scientific_apis` with a bounded `1.5s` socket timeout and `PKDE_OFFLINE=1` short-circuit), returning `execution_mode` (`"full"` | `"degraded_offline"` | `"blocked"`).
3. **Hermetic Python & Sandbox-Safe File I/O**: `bin/env.sh`, `bin/pkde`, `bin/pkde-mcp`, `bin/prox`, and `pkde_plugin/tool_bridge.py` prefer `$PKDE_ROOT/.venv/bin/python` and isolate `PYTHONPATH` (`$PKDE_ROOT:$PKDE_ROOT/tools:$PKDE_ROOT/tools/vendor/hypex`) from host site-packages. Dashboard HTML generation (`_safe_write_html`) falls back safely when `os.replace()` is restricted.
4. **Security, Network Isolation & Path Confinement**:
   - All file operations are confined to the active project workspace (`tools/pkde/core/paths.py`), and `resolve_live_project_root` confines active workspace pointers inside the repository root.
   - The local HTTP/SSE dashboard server binds to `127.0.0.1` by default, attaches `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and `Cross-Origin-Resource-Policy: same-origin` headers, enforces same-origin `Origin` checks on `/api/bundle` and `/api/stream`, and validates process identity before sending `SIGTERM`.
   - `dashboard.html` and all 14 static HTML viewers operate with zero external CDN or web-font requests, strict `<meta http-equiv="Content-Security-Policy">`, same-origin `?file=` path validation, sanitized Markdown rendering, and delegated event handlers (no inline dynamic `onclick` string interpolation).
   - Optional cloud prediction backends (`alphafold predict`, `alphagenome`) require explicit environment variable configuration (`PKDE_AF3_PROJECT`, `PKDE_AG_PROJECT`, `PKDE_AG_ENDPOINT_ID`, `PKDE_AG_ENDPOINT_DNS`) with no hardcoded internal project defaults.
5. **Accessibility (WCAG 2.2 AA)**: Both `dashboard.html` and static dossier pages (`base.html`) enforce >= `4.5:1` normal-text contrast in Light and Dark modes, semantic landmarks (`<header>`, `<nav>`, `<main>`, `<footer>`), non-skipping heading hierarchies, visible `:focus-visible` outlines, keyboard activation on all interactive controls, and explicit textual status prefixes (`[ERROR]`, `[WARN]`, `[FAIL]`).
6. **Rate Limiting & Environment Reproducibility**: Outbound HTTP requests enforce per-host QPS pacing (`tools/pkde/core/qps.py`), and every provenance sidecar records `tools/ENV_VERSION` covering the Python interpreter, locked packages, wrapper scripts, and multi-architecture static binaries.

---

## 6. Verification & Acceptance Criteria

The build and test suite (`tests/`, 9 test modules) verifies:
- `tests/test_custom_byoa.py`: Two-phase private CSV ingestion (`pkde custom ingest`), proprietary algorithm execution (`pkde custom run`), offline evaluation (`pkde custom analyze`), relay attribution (`pkde relays`), and dynamic Click extension loading.
- `tests/test_pocket_geometric.py`: Built-in Python/NumPy geometric pocket detector (`pkde pocket run --backend [geometric|auto]`), offline `pkde pocket analyze`, relay propagation, and docking grid-box compatibility.
- `tests/test_targets_compile.py`: Compilation of all 43 skills and 22 agent templates into `.agents/plugins/pharmakon-discovery-engine/` and `dist/skill-bundles/*.zip`, root-vs-skill script/reference parity, and multi-architecture binary verification.
- `tests/test_tool_bridge.py`: `pkde_exec`, `pkde_dispatch_workorder`, `pkde_validate_and_gate`, hermetic `PYTHONPATH` isolation, `pkde doctor` offline detection, stdlib MCP fallback, and MCP `ToolAnnotations`.
- `tests/test_dashboard.py`: Standalone `dashboard.html` generation, sandbox-safe atomic writes, live server lifecycle, theme tokens, host OS theme detection, offline 3D/2D rendering, and all 20 scientific visualization studios.
- `tests/test_real_execution_anti_echo.py`: Positive/negative computational math controls across RDKit, NCA PK integration, geometric pocket detection, native `hypex`/`elo`/`prox` execution, and SHA-256 tamper detection.
- `tests/test_multi_agent_cohort_and_no_stubs.py`: AST/source surface coverage, multi-persona cohort dispatch waves, subagent binding, Wave 2 promotion, dependency cycle rejection, and MCP cohort registration.
- `tests/test_skill_contract.py`: CLI-to-bridge-to-MCP parity across `dispatch_workorder.py`, `tool_bridge.py`, and `mcp_server.py`, work-order schema validation, lease TTL expiration/renewal, and Click flag alignment.
- `tests/test_security_and_a11y.py`: Zero external CDN/font references, repository sanitization and absolute-path checks, HTTP security headers and cross-origin `403` rejection, Markdown XSS blocking, viewer `?file=` same-origin guards, MCP fallback strict argument rejection, cloud env-var requirements, and WCAG 2.2 AA contrast/landmark/heading/focus checks.



