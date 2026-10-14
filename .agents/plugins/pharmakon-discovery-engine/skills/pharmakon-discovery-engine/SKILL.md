---
name: pharmakon-discovery-engine
description: "Primary agent harness skill for pre-clinical drug discovery and target evaluation (Stages 0-4). Activate for any question or campaign involving target biology, human genetics (gnomAD/GWAS/OpenTargets), protein structure & pockets (AlphaFold 3/PDB/fpocket), medicinal chemistry & ADMET (RDKit/ChEMBL/SAR/MPO), docking (Vina), DMPK/toxicology, clinical/competitive landscape, hypothesis tournaments (Co-Scientist/Hypex), custom datasets/algorithms (BYOA), or multi-agent PkDE work orders."
metadata:
  display_name: Pharmakon Discovery Engine (PkDE) Orchestrator & Harness
---

# Pharmakon Discovery Engine (PkDE) Orchestrator & Harness

The **Pharmakon Discovery Engine (`pharmakon-discovery-engine`)** skill provides a portable, two-phase scientific execution and multi-agent work-order harness for end-to-end pre-clinical drug discovery, target evaluation, and custom data/algorithm integration.

## Core Architectural Invariants

1. **Hermetic & Portable Environment Setup**:
   Always source `./bin/env.sh` from the repository root (or invoke commands via `./bin/pkde`, `pkde_exec`, or `scripts/pkde_runner.py`). `./bin/env.sh` and `./bin/pkde` automatically prefer `$PKDE_ROOT/.venv/bin/python` and isolate `PYTHONPATH` from incompatible host site-packages:
   ```bash
   source ./bin/env.sh
   ```
2. **Step 0 -- Immediate Prompt-to-Dashboard Bootstrap (`0.0.0.0:8765`) & Preflight Readiness Gate**:
   As the **very first action** upon receiving a user prompt:
   ```bash
   ./bin/pkde dashboard start --prompt "<user prompt>" --host 0.0.0.0 --port 8765 --json
   # Or via the bundled helper script (available atboth ./scripts/ and skills/pharmakon-discovery-engine/scripts/):
   ./.venv/bin/python scripts/start_live_session.py --prompt "<user prompt>"
   # Run preflight environment & network readiness check:
   ./bin/pkde doctor --json
   ```
   - **Preflight & Degraded-Mode Gate (`execution_mode`)**: Inspect `"execution_mode"` in `./bin/pkde doctor --json`:
     - `"full"`: Both local compute and external scientific APIs are reachable. Proceed normally.
     - `"degraded_offline"`: Outbound scientific APIs are blocked by the container/sandbox (`network_reachable: false`).
       - **DO NOT** dispatch Work Orders that require fetching from external online databases (`genetics`, `gwas`, `alphafold`, `pubchem`, `literature`, `trials`, `expression`, `geo`, `cellxgene`, etc.).
       - **DO NOT** create empty Work Orders or advance/evaluate Stage Gate Packages with `0/N` populated evidence slots.
       - If the user provided local files or custom scripts/data, run local-compute tools only (`pkde custom`, `compound`, `assay`, `selectivity`, `mmp`, `mpo`, `pk`, `tox`, `pocket`, `docking`).
       - If the user's prompt requires online database retrieval and no local files were supplied, **HALT IMMEDIATELY** before creating any Work Orders and report `ENVIRONMENT_BLOCKED: Sandbox blocks outbound scientific APIs (execution_mode=degraded_offline)`.
     - `"blocked"`: Core Python or toolchain integrity checks failed (`ok: false`). Halt and report the failed checks from `pkde doctor`.
3. **Mandatory Two-Phase Scientific Execution & Zero-Overhead Passive Telemetry**:
   Every PkDE domain command group (`genetics`, `gwas`, `alphagenome`, `expression`, `gtex`, `cellxgene`, `geo`, `allen`, `phenotype`, `pathway`, `alphafold`, `structure`, `pocket`, `ppi`, `conservation`, `homology`, `compound`, `analog`, `similar`, `mmp`, `mpo`, `retro`, `pubchem`, `docking`, `screen`, `structure_screen`, `admet`, `pk`, `assay`, `selectivity`, `tox`, `faers`, `trials`, `patent`, `differentiation`, `manufacturing`, `coscientist`, `hypex`, `hypothesis`, `custom`) operates in two strict phases:
   - **Phase 1 (`fetch` / `run` / `compute` / `search` / `predict` / `generate` / `ingest`)**: Produces immutable **Layer 0** raw data (`raw/<category>/<stem>.<ext>`) and a cryptographic SHA-256 provenance sidecar (`<stem>.meta.json`).
   - **Phase 2 (`analyze`)**: Evaluates Phase 1 outputs against domain thresholds in `tools/pkde/core/thresholds.py` and writes `<stem>.analysis.json` containing `verdict`, `summary`, `thresholds_applied`, and `mandatory_relays`.
   - **Passive CLI & Filesystem Telemetry**: The `pkde` CLI dispatcher automatically logs `tool.started`, `tool.completed`, and `tool.failed` events (`<0.5ms` overhead) to `.pkde/control/events.ndjson`, and the live server automatically detects new Layer 1 findings (`findings/**/*.md`), Layer 2 program-state updates (`program-state/*.md`), and Layer 4 executive summaries (`executive/program-summary.md`). Do not make extra tool calls solely to log telemetry.
4. **Mandatory Relays & Inline Source Provenance**:
   Every entry in `mandatory_relays` inside `<stem>.analysis.json` **must** appear verbatim in the corresponding Layer 1 Markdown report (`findings/<discipline>/<topic>.md`) as `**Relay: \`<code>\`**`, and every quantitative claim must carry an inline `{source: raw/<category>/<file>#$.json.path}` citation.
5. **Live Auto-Populating Dashboard & 4 View Modes (`Split` | `Agents` | `Discovery` | `Telemetry`)**:
   - The dashboard provides **4 top-bar view modes** (`Split`, `Agents`, `Discovery`, and `Telemetry`) plus a persistent collapsible **Live Telemetry Console** drawer at the bottom of `Split`, `Agents`, and `Discovery` views.
   - Clicking any one-liner in the Live Telemetry Console or the 4th `Telemetry` view automatically deep-navigates to the corresponding Agent node, Layer 1 Specialist Finding, Layer 0 Interactive Scientific Studio, or Mandatory Relay table.
   - Differential DOM updates ensure active `3Dmol.js` WebGL cameras, `Plotly.js` charts, Findings reader scroll positions, and SVG pan/zoom states never reset while live telemetry streams in.

---

## Execution Modes

### Mode 1 -- Interactive Scientific Q&A ("Fast-Path PkDE Questions")

Use **Mode 1** when the user asks a focused, single-domain scientific question about a target, gene, protein structure, compound SMILES, SAR series, ADMET liability, or Stage 0 triage scorecard.

1. **Step 0 -- Bootstrap Live Dashboard Session (`0.0.0.0:8765`) & Preflight Check**:
   Run `./bin/pkde dashboard start --prompt "<user prompt>" --json` and `./bin/pkde doctor --json` (confirm `execution_mode` supports the required tools).
2. **Two-Phase Domain Tool Execution**:
   Run Phase 1 followed immediately by Phase 2 (`analyze`), or spin up the matching specialist subagent (`pkde-<role>`):
   ```bash
   # Example: Target genetic evidence for EGFR (requires execution_mode == "full")
   ./bin/pkde genetics fetch EGFR --json
   ./bin/pkde genetics analyze EGFR --json

   # Example: Compound property & ADMET profiling (works in both "full" and "degraded_offline")
   ./bin/pkde compound profile "CC(=O)Oc1ccccc1C(=O)O" --name aspirin --json
   ./bin/pkde compound analyze aspirin --json
   ./bin/pkde admet predict "CC(=O)Oc1ccccc1C(=O)O" --name aspirin --json
   ./bin/pkde admet analyze aspirin --json
   ```
3. **Surface Mandatory Relays**:
   Inspect the generated `.analysis.json` sidecar and include all `mandatory_relays` codes verbatim (`**Relay: \`<code>\`**`) in your response and findings report.
4. **Verify `dashboard.html` Update**:
   Every CLI execution automatically refreshes `dashboard.html` and pushes a live SSE update to `http://0.0.0.0:8765`; you may also run `./bin/pkde dashboard build --standalone --json` (or `pkde_render_dashboard()`) at the end of the turn to confirm the final snapshot.

---

### Mode 2 -- Full Multi-Agent Program / Cohort Mode

Use **Mode 2** whenever the scientific task spans multiple disciplines (e.g., target genetics + 3D structure/pockets + medicinal chemistry/ADMET + molecular docking + preclinical safety, or a multi-agent Hypex tournament). In this mode, the skill acts as the **Science Program Lead & Research Operations Controller** and spins up multiple specialist subagents in parallel:

1. **Step 0 -- Bootstrap Live Dashboard Session (`0.0.0.0:8765`), Doctor Preflight & Charter**:
   - Run `./bin/pkde dashboard start --prompt "<user prompt>" --program-name "<Program Name>" --stage 1 --json` and `./bin/pkde doctor --json`.
   - **Check `execution_mode`**: If `"degraded_offline"` and the campaign requires online fetches without local input files, halt immediately and report `ENVIRONMENT_BLOCKED` before creating Work Orders.
   - Otherwise, record the program charter in `program-state/decision-log.md` (`DEC-001`).
2. **Step 1 -- Atomic Work-Order Dispatch (Populates Running Agent Nodes in `dashboard.html`)**:
   - Consult `references/role-skill-matrix.md` and `references/stage0-3-playbook.md` for role assignments and deliverable conventions.
   - For each specialist discipline needed for the scientific task, dispatch the Work Order using **any** of the three equivalent interfaces (CLI subcommand, bundled script, or MCP tool):
     ```bash
     # Option A — Native pkde CLI (always available):
     ./bin/pkde workorder dispatch --spec '<inline-json-or-yaml-path>' --json
     # Option B — Bundled helper script:
     ./.venv/bin/python scripts/dispatch_workorder.py --spec '<inline-json-or-yaml-path>'
     # Option C — MCP tool (when MCP server pkde-engine is active):
     # pkde_dispatch_workorder(spec={...})
     ```
   - This atomically:
     1. Creates and commits `WO-NNN-r1` (`pkde workorder create --from <yaml> --commit --json`).
     2. Freezes the checksummed context snapshot in `.pkde/control/contexts/WO-NNN-r1.json`.
     3. Acquires any required resource lease in `.pkde/control/leases/<resource_class>.json` (`af3`, `hypex-supervisor`).
     4. Creates `RUN-NNN`, transitions `queued -> starting -> running` (`in_progress`), and immediately updates `dashboard.html` and `http://0.0.0.0:8765` so each dispatched specialist appears as an active `running` node in the Multi-Agent Lineage Graph.
3. **Step 2 -- Spin Up Multiple Specialist Subagents in Parallel**:
   - Launch all dispatched specialist subagents concurrently in a single `invoke_subagent` call (`Subagents=[{"TypeName": "pkde-<requested_role>", "Role": "...", "Prompt": dispatch_result["specialist_brief"]}, ...]`).
   - Available specialist roles (`pkde-<role>`): `pkde-computational-biologist`, `pkde-structural-biologist`, `pkde-medicinal-chemist`, `pkde-computational-chemist`, `pkde-admet-dmpk-scientist`, `pkde-experimental-biologist`, `pkde-preclinical-toxicologist`, `pkde-regulatory-scientist`, `pkde-scientific-reviewer`, and the `pkde-hypex-*` tournament cohort (`pkde-hypex-supervisor`, `pkde-hypex-generation`, `pkde-hypex-reflection`, `pkde-hypex-proximity`, `pkde-hypex-tournament`, `pkde-hypex-evolution`, `pkde-hypex-meta-review`).
   - As each subagent executes its Phase 1 and Phase 2 `pkde` CLI commands and writes its Layer 1 finding (`findings/<discipline>/<slug>.md`), passive CLI and filesystem telemetry automatically streams into `http://0.0.0.0:8765` and updates `dashboard.html`.
4. **Step 3 -- 10-Check Mechanical Validation & Correction Loop**:
   - When each specialist subagent finishes, run the validation gate via CLI or MCP:
     ```bash
     # Native CLI:
     ./bin/pkde workorder validate-and-gate <WO-ID> --run-id <RUN-ID> --json
     # Or via MCP tool: pkde_validate_and_gate(work_order_id="<WO-ID>", run_id="<RUN-ID>")
     ```
     This runs `pkde validate check <WO-ID> --json` across all 10 checks (`deliverables_exist`, `report_headings`, `paths_resolve`, `provenance_valid`, `analysis_citations`, `relay_coverage`, `version_policy`, `findings_integrity`, `source_tags_resolve`, `unrecognized_json`) and updates the node's validation matrix in `dashboard.html`.
   - If `status == "CORRECTION_REQUIRED"` (mechanical defect, cycle <= 2), send `correction_prompt` back to that specialist subagent (`send_message(Recipient=subagent_id, Message=correction_prompt)`) to fix the defect in-place and re-run `./bin/pkde workorder validate-and-gate <WO-ID> --json`.
   - If `status == "DATA_INTEGRITY_FAILURE"`, halt the run immediately (no retry allowed) and log the escalation in `program-state/decision-log.md`.
5. **Step 4 -- Independent Scientific Review & Layer 2/4 Synthesis**:
   - For mechanically validated work orders (`mechanically_validated`), invoke `pkde-scientific-reviewer` to re-run Phase 2 (`analyze --out raw/reanalysis/<date>-reviewer/`) and write `findings/reviews/<finding>-review.md`.
   - Accept validated work orders via `./bin/pkde workorder accept <WO-ID>`, and update Layer 2 (`program-state/active-series.md`, `liability-tracker.md`, `decision-log.md`, `open-questions.md`) and Layer 4 (`executive/program-summary.md`).
6. **Step 5 -- Final `dashboard.html` Publication**:
   - Run `./bin/pkde dashboard build --standalone --json` so `dashboard.html` reflects the completed multi-agent lineage graph, telemetry history, and all scientific studios.

---

### Mode 3 -- Custom Data Ingestion & Bring-Your-Own-Algorithm (BYOA)

Use **Mode 3** whenever the user supplies proprietary/custom datasets (`.csv`, `.tsv`, `.json`, `.jsonl`, `.sdf`) or custom Python scoring, ranking, or scientific computation scripts (`.py`). All custom data and algorithms preserve the full PkDE two-phase provenance contract (`raw/custom/<name>.json` + `.meta.json` + `.analysis.json`):

1. **Two-Phase Custom Data Ingestion (`pkde custom ingest` -> `pkde custom analyze`)**:
   ```bash
   # Phase 1: Ingest custom CSV/TSV/JSON/JSONL/SDF into Layer 0 with SHA-256 provenance
   ./bin/pkde custom ingest <path/to/data.csv> \
     --name <dataset_slug> \
     --domain <chemistry|biology|dmpk|tox|clinical|custom> \
     --id-column <id_col> \
     --description "User-supplied screening dataset" \
     --json

   # Phase 2: Analyze, rank, and apply threshold gates on any numeric metric column
   ./bin/pkde custom analyze \
     --name <dataset_slug> \
     --metric-column <score_col> \
     --target-direction <higher|lower> \
     --threshold <cutoff_value> \
     --json
   ```
2. **Two-Phase Custom Algorithm / Ranking Script Execution (`pkde custom run` -> `pkde custom analyze`)**:
   - Custom Python scripts receive three environment variables from `pkde custom run`:
     - `PKDE_CUSTOM_INPUT`: Path to the input dataset file (if `--input` is passed).
     - `PKDE_CUSTOM_OUTPUT`: Path where the script can write its JSON output (or the script can print JSON to `stdout`).
     - `PKDE_CUSTOM_PARAMS`: JSON-encoded parameters passed via `--params`.
   - Both the input file SHA-256 and the custom script SHA-256 are cryptographically stamped into `raw/custom/<name>.json.meta.json`.
   ```bash
   # Phase 1: Execute custom ranking/computation script in a hermetic subprocess
   ./bin/pkde custom run \
     --script <path/to/custom_ranker.py> \
     --input <path/to/input.csv> \
     --name <run_slug> \
     --domain chemistry \
     --params '{"weights": {"potency": 0.6, "solubility": 0.4}}' \
     --json

   # Phase 2: Evaluate custom algorithm output and emit mandatory relays
   ./bin/pkde custom analyze \
     --name <run_slug> \
     --metric-column composite_score \
     --target-direction higher \
     --threshold 0.70 \
     --json
   ```
   - `pkde custom analyze` emits standard relays (`CUSTOM_METRIC_THRESHOLD_BREACH`, `CUSTOM_SMALL_SAMPLE_WARNING`) that must be surfaced in Layer 1 findings and automatically render in the Interactive Dashboard's **Custom Data & BYOA Studio**.
3. **Persistent Drop-In Skill & Role Extensions (`extensions/`)**:
   - Place reusable custom skills in `extensions/skills/<skill-name>/SKILL.md` and map them to specialist roles in `extensions/role-grants.yaml`, then run `./.venv/bin/python pkde_plugin/build_targets.py` to compile them into `.agents/plugins/pharmakon-discovery-engine/` and `dist/skill-bundles/`.

---

## Bundled Scripts & References

Available both at the repository root (`./scripts/`, `./references/`) and inside `skills/pharmakon-discovery-engine/`:

- `scripts/start_live_session.py`: Bootstraps a live PkDE session from the user prompt and ensures the non-blocking background server on `0.0.0.0:8765` is running.
- `scripts/pkde_runner.py`: Portable CLI wrapper that executes any `pkde` command with automatic environment discovery and dashboard refresh.
- `scripts/dispatch_workorder.py`: CLI helper for atomic Work Order intake, snapshot creation, lease check, and specialist brief generation (equivalent to `./bin/pkde workorder dispatch`).
- `references/role-skill-matrix.md`: Complete mapping of all 22 PkDE roles (`pkde-<role>`) to their categories, domain tools, and injected skill lanes.
- `references/stage0-3-playbook.md`: Stage 0-3 decision gates, degraded-mode offline rules, deliverable templates, and 10-check validation checklist.
