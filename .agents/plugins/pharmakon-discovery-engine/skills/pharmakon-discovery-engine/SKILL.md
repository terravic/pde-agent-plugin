---
name: pharmakon-discovery-engine
description: "Primary agent harness skill for pre-clinical drug discovery and target evaluation (Stages 0-4). Activate for any question or campaign involving target biology, human genetics (gnomAD/GWAS/OpenTargets), protein structure & pockets (AlphaFold 3/PDB/fpocket), medicinal chemistry & ADMET (RDKit/ChEMBL/SAR/MPO), docking (Vina), DMPK/toxicology, clinical/competitive landscape, hypothesis tournaments (Co-Scientist/Hypex), or multi-agent PDE work orders."
metadata:
  display_name: Pharmakon Discovery Engine (PDE) Orchestrator & Harness
---

# Pharmakon Discovery Engine (PDE) Orchestrator & Harness

The **Pharmakon Discovery Engine (`pharmakon-discovery-engine`)** skill provides a portable, two-phase scientific execution and multi-agent work-order harness for end-to-end pre-clinical drug discovery and target evaluation.

## Core Architectural Invariants

1. **Portable Environment Setup**:
   Always source `./bin/env.sh` from the repository root (or invoke commands via `pde_exec` / `scripts/pde_runner.py`):
   ```bash
   source ./bin/env.sh
   ```
2. **Step 0 -- Immediate Prompt-to-Dashboard Bootstrap (`0.0.0.0:8765`)**:
   As the **very first action** upon receiving a user prompt, initialize the live session and start the non-blocking background HTTP + Server-Sent Events (SSE) server on `0.0.0.0:8765`:
   ```bash
   ./bin/pde dashboard start --prompt "<user prompt>" --host 0.0.0.0 --port 8765 --json
   # Or via the bundled helper script / MCP tool:
   python3 skills/pharmakon-discovery-engine/scripts/start_live_session.py --prompt "<user prompt>"
   ```
   This returns in `<100ms`, records the user's prompt in `.pde/program.yaml` and `.pde/control/events.ndjson`, builds the initial `dashboard.html` with the `user -> science-program-lead` root nodes and Active Session Prompt Charter, and starts the background SSE server at `http://0.0.0.0:8765` so the user can open the browser immediately and watch every agent creation, inter-agent communication, CLI command, and discovery finding stream live.
3. **Mandatory Two-Phase Scientific Execution & Zero-Overhead Passive Telemetry**:
   Every PDE domain command group (`genetics`, `gwas`, `alphagenome`, `expression`, `gtex`, `cellxgene`, `geo`, `allen`, `phenotype`, `pathway`, `alphafold`, `structure`, `pocket`, `ppi`, `conservation`, `homology`, `compound`, `analog`, `similar`, `mmp`, `mpo`, `retro`, `pubchem`, `docking`, `screen`, `structure_screen`, `admet`, `pk`, `assay`, `selectivity`, `tox`, `faers`, `trials`, `patent`, `differentiation`, `manufacturing`, `coscientist`, `hypex`, `hypothesis`, `custom`) operates in two strict phases:
   - **Phase 1 (`fetch` / `run` / `compute` / `search` / `predict` / `generate` / `ingest`)**: Produces immutable **Layer 0** raw data (`raw/<category>/<stem>.<ext>`) and a cryptographic SHA-256 provenance sidecar (`<stem>.meta.json`).
   - **Phase 2 (`analyze`)**: Evaluates Phase 1 outputs against domain thresholds in `tools/pde/core/thresholds.py` and writes `<stem>.analysis.json` containing `verdict`, `summary`, `thresholds_applied`, and `mandatory_relays`.
   - **Passive CLI & Filesystem Telemetry**: The `pde` CLI dispatcher automatically logs `tool.started`, `tool.completed`, and `tool.failed` events (`<0.5ms` overhead) to `.pde/control/events.ndjson`, and the live server automatically detects new Layer 1 findings (`findings/**/*.md`), Layer 2 program-state updates (`program-state/*.md`), and Layer 4 executive summaries (`executive/program-summary.md`). Do not make extra tool calls solely to log telemetry.
4. **Mandatory Relays & Inline Source Provenance**:
   Every entry in `mandatory_relays` inside `<stem>.analysis.json` **must** appear verbatim in the corresponding Layer 1 Markdown report (`findings/<discipline>/<topic>.md`) as `**Relay: \`<code>\`**`, and every quantitative claim must carry an inline `{source: raw/<category>/<file>#$.json.path}` citation.
5. **Live Auto-Populating Dashboard & 4 View Modes (`Split` | `Agents` | `Discovery` | `Telemetry`)**:
   - The dashboard provides **4 top-bar view modes** (`Split`, `Agents`, `Discovery`, and `Telemetry`) plus a persistent collapsible **Live Telemetry Console** drawer at the bottom of `Split`, `Agents`, and `Discovery` views.
   - Clicking any one-liner in the Live Telemetry Console or the 4th `Telemetry` view automatically deep-navigates to the corresponding Agent node, Layer 1 Specialist Finding, Layer 0 Interactive Scientific Studio, or Mandatory Relay table.
   - Differential DOM updates ensure active `3Dmol.js` WebGL cameras, `Plotly.js` charts, Findings reader scroll positions, and SVG pan/zoom states never reset while live telemetry streams in.

---

## Execution Modes

### Mode 1 -- Interactive Scientific Q&A ("Fast-Path PDE Questions")

Use **Mode 1** when the user asks a focused, single-domain scientific question about a target, gene, protein structure, compound SMILES, SAR series, ADMET liability, or Stage 0 triage scorecard.

1. **Step 0 -- Bootstrap Live Dashboard Session (`0.0.0.0:8765`)**:
   Run `./bin/pde dashboard start --prompt "<user prompt>" --json` (or `pde_bootstrap_session(prompt=...)`) so `http://0.0.0.0:8765` is immediately live with the user's prompt.
2. **Two-Phase Domain Tool Execution**:
   Run Phase 1 followed immediately by Phase 2 (`analyze`), or spin up the matching specialist subagent (`pde-<role>`):
   ```bash
   # Example: Target genetic evidence for EGFR
   ./bin/pde genetics fetch EGFR --json
   ./bin/pde genetics analyze EGFR --json

   # Example: Compound property & ADMET profiling
   ./bin/pde compound profile "CC(=O)Oc1ccccc1C(=O)O" --name aspirin --json
   ./bin/pde compound analyze aspirin --json
   ./bin/pde admet predict "CC(=O)Oc1ccccc1C(=O)O" --name aspirin --json
   ./bin/pde admet analyze aspirin --json
   ```
3. **Surface Mandatory Relays**:
   Inspect the generated `.analysis.json` sidecar and include all `mandatory_relays` codes verbatim (`**Relay: \`<code>\`**`) in your response and findings report.
4. **Verify `dashboard.html` Update**:
   Every CLI execution automatically refreshes `dashboard.html` and pushes a live SSE update to `http://0.0.0.0:8765`; you may also call `pde_render_dashboard()` (or `./bin/pde dashboard build --standalone --json`) at the end of the turn to confirm the final snapshot.

---

### Mode 2 -- Full Multi-Agent Program / Cohort Mode

Use **Mode 2** whenever the scientific task spans multiple disciplines (e.g., target genetics + 3D structure/pockets + medicinal chemistry/ADMET + molecular docking + preclinical safety, or a multi-agent Hypex tournament). In this mode, the skill acts as the **Science Program Lead & Research Operations Controller** and spins up multiple specialist subagents in parallel:

1. **Step 0 -- Bootstrap Live Dashboard Session (`0.0.0.0:8765`) & Charter**:
   - Run `./bin/pde dashboard start --prompt "<user prompt>" --program-name "<Program Name>" --stage 1 --json` (or `python3 skills/pharmakon-discovery-engine/scripts/start_live_session.py --prompt "<user prompt>"`), run `./bin/pde doctor --json`, and record the program charter in `program-state/decision-log.md` (`DEC-001`). This immediately creates `dashboard.html` and starts `http://0.0.0.0:8765` with the `user` and `science-program-lead` root nodes.
2. **Step 1 -- Atomic Work-Order Dispatch (Populates Running Agent Nodes in `dashboard.html`)**:
   - For each specialist discipline needed for the scientific task, call `pde_dispatch_workorder(spec)` (or run `python3 skills/pharmakon-discovery-engine/scripts/dispatch_workorder.py --spec <spec.json>`).
   - This atomically:
     1. Creates and commits `WO-NNN-r1` (`pde workorder create --from <yaml> --commit --json`).
     2. Freezes the checksummed context snapshot in `.pde/control/contexts/WO-NNN-r1.json`.
     3. Acquires any required resource lease in `.pde/control/leases/<resource_class>.json` (`af3`, `hypex-supervisor`).
     4. Creates `RUN-NNN`, transitions `queued -> starting -> running` (`in_progress`), and immediately updates `dashboard.html` and `http://0.0.0.0:8765` so each dispatched specialist appears as an active `running` node in the Multi-Agent Lineage Graph.
3. **Step 2 -- Spin Up Multiple Specialist Subagents in Parallel**:
   - Launch all dispatched specialist subagents concurrently in a single `invoke_subagent` call (`Subagents=[{"TypeName": "pde-<requested_role>", "Role": "...", "Prompt": dispatch_result["specialist_brief"]}, ...]`).
   - Available specialist roles (`pde-<role>`): `pde-computational-biologist`, `pde-structural-biologist`, `pde-medicinal-chemist`, `pde-computational-chemist`, `pde-admet-dmpk-scientist`, `pde-experimental-biologist`, `pde-preclinical-toxicologist`, `pde-regulatory-scientist`, `pde-scientific-reviewer`, and the `pde-hypex-*` tournament cohort (`pde-hypex-supervisor`, `pde-hypex-generation`, `pde-hypex-reflection`, `pde-hypex-proximity`, `pde-hypex-tournament`, `pde-hypex-evolution`, `pde-hypex-meta-review`).
   - As each subagent executes its Phase 1 and Phase 2 `pde` CLI commands and writes its Layer 1 finding (`findings/<discipline>/<slug>.md`), passive CLI and filesystem telemetry automatically streams into `http://0.0.0.0:8765` and updates `dashboard.html`.
4. **Step 3 -- 10-Check Mechanical Validation & Correction Loop**:
   - When each specialist subagent finishes, call `pde_validate_and_gate(work_order_id, run_id)` (which runs `pde validate check <WO-ID> --json` across all 10 checks: `deliverables_exist`, `report_headings`, `paths_resolve`, `provenance_valid`, `analysis_citations`, `relay_coverage`, `version_policy`, `findings_integrity`, `source_tags_resolve`, `unrecognized_json` and updates the node's validation matrix in `dashboard.html`).
   - If `status == "CORRECTION_REQUIRED"` (mechanical defect, cycle <= 2), send `correction_prompt` back to that specialist subagent (`send_message(Recipient=subagent_id, Message=correction_prompt)`) to fix the defect in-place and re-run `pde_validate_and_gate`.
   - If `status == "DATA_INTEGRITY_FAILURE"`, halt the run immediately (no retry allowed) and log the escalation in `program-state/decision-log.md`.
5. **Step 4 -- Independent Scientific Review & Layer 2/4 Synthesis**:
   - For mechanically validated work orders (`mechanically_validated`), invoke `pde-scientific-reviewer` to re-run Phase 2 (`analyze --out raw/reanalysis/<date>-reviewer/`) and write `findings/reviews/<finding>-review.md`.
   - Accept validated work orders via `pde workorder accept <WO-ID>`, and update Layer 2 (`program-state/active-series.md`, `liability-tracker.md`, `decision-log.md`, `open-questions.md`) and Layer 4 (`executive/program-summary.md`).
6. **Step 5 -- Final `dashboard.html` Publication**:
   - Run `./bin/pde dashboard build --standalone --json` so `dashboard.html` reflects the completed multi-agent lineage graph, telemetry history, and all 20 scientific studios.

---

## Bundled Scripts & References

- `scripts/start_live_session.py`: Bootstraps a live PDE session from the user prompt and ensures the non-blocking background server on `0.0.0.0:8765` is running.
- `scripts/pde_runner.py`: Portable CLI wrapper that executes any `pde` command with automatic environment discovery and dashboard refresh.
- `scripts/dispatch_workorder.py`: CLI helper for atomic Work Order intake, snapshot creation, lease check, and specialist brief generation.
- `references/role-skill-matrix.md`: Complete mapping of all 22 PDE roles (`pde-<role>`) to their categories, domain tools, and injected skill lanes.
- `references/stage0-3-playbook.md`: Stage 0-3 decision gates, deliverable templates, and 10-check validation checklist.
