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
   # Or via the bundled helper script (available at both ./scripts/ and skills/pharmakon-discovery-engine/scripts/):
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
3. **Mandatory Two-Phase Scientific Execution & Automatic Passive Telemetry**:
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
   ./bin/pkde compound analyze --name aspirin --json
   ./bin/pkde admet predict "CC(=O)Oc1ccccc1C(=O)O" --name aspirin --json
   ./bin/pkde admet analyze "CC(=O)Oc1ccccc1C(=O)O" --name aspirin --json
   ```
3. **Surface Mandatory Relays**:
   Inspect the generated `.analysis.json` sidecar and include all `mandatory_relays` codes verbatim (`**Relay: \`<code>\`**`) in your response and findings report.
4. **Verify `dashboard.html` Update**:
   Every CLI execution automatically refreshes `dashboard.html` and pushes a live SSE update to `http://0.0.0.0:8765`; you may also run `./bin/pkde dashboard build --standalone --json` (or `pkde_render_dashboard()`) at the end of the turn to confirm the final snapshot.

---

### Mode 2 -- Full Multi-Agent Program / Cohort Mode

Use **Mode 2** whenever the scientific task spans multiple disciplines (e.g., target genetics + 3D structure/pockets + medicinal chemistry/ADMET + molecular docking + preclinical safety, or a multi-agent Hypex tournament). In this mode, the skill acts as the **Science Program Lead & Research Operations Controller** and spins up multiple specialist subagents in parallel:

1. **Step 0 -- Bootstrap Live Dashboard Session (`0.0.0.0:8765`), Doctor Preflight & Charter**:
   - Run `./bin/pkde dashboard start --prompt "<user prompt>" --name "<Program Name>" [--target <GENE>] [--indication "<disease>"] [--modality <modality>] --stage 1 --json` and `./bin/pkde doctor --json`.
   - **Check `execution_mode`**: If `"degraded_offline"` and the campaign requires online fetches without local input files, halt immediately and report `ENVIRONMENT_BLOCKED` before creating Work Orders.
   - Otherwise, record the program charter in `program-state/decision-log.md` (`DEC-001`).
2. **Step 1 -- Atomic Single or Multi-Persona Cohort Work-Order Dispatch (Populates Running & Queued Wave Nodes in `dashboard.html`)**:
   - Consult `references/role-skill-matrix.md` and `references/stage0-3-playbook.md` for role assignments and deliverable conventions.
   - **Every spec must state its science explicitly -- nothing is defaulted.** Required per spec:
     - `requested_role` (alias `role`): one of the 22 `pkde-<role>` agents (prefix optional). Unknown roles are rejected.
     - `decision_question`: the concrete question this specialist must answer from the user's prompt.
     - `deliverables.layer_1`: findings report path(s), e.g. `findings/computational-biology/egfr-genetics.md`.
     - `deliverables.layer_0_classes`: the Layer 0 evidence classes the specialist must produce with `pkde` tools (e.g. `["genomics"]`). Review/synthesis work orders that only cite upstream artifacts set `deliverables.synthesis_only: true` instead.
     - Optional: `spec_id` (alias for `depends_on`), `depends_on`, `context`, `stage`, `cycle`, `resource_class` (`standard` | `af3` | `hypex-supervisor`), `priority`, `acceptance_criteria`.
     ```json
     [
       {"spec_id": "genetics", "requested_role": "computational-biologist",
        "decision_question": "Is EGFR genetically constrained and disease-associated in NSCLC?",
        "deliverables": {"layer_0_classes": ["genomics"], "layer_1": ["findings/computational-biology/egfr-genetics.md"]}},
       {"spec_id": "structure", "requested_role": "structural-biologist",
        "decision_question": "Does EGFR's kinase domain have a druggable, well-resolved pocket?",
        "deliverables": {"layer_0_classes": ["structures"], "layer_1": ["findings/structural-biology/egfr-pockets.md"]}},
       {"spec_id": "review", "requested_role": "scientific-reviewer", "depends_on": ["genetics", "structure"],
        "decision_question": "Do the genetics and structure findings support nominating EGFR?",
        "deliverables": {"synthesis_only": true, "layer_1": ["findings/reviews/egfr-nomination-review.md"]}}
     ]
     ```
   - Dispatch the entire cohort at once using **any** of the three equivalent interfaces (CLI subcommand, bundled script, or MCP tool):
     ```bash
     # Multi-Persona Cohort Dispatch (partitions into Wave 1 parallel running + Wave 2+ queued by dependencies & resource leases):
     ./bin/pkde workorder dispatch-cohort --specs '[<spec-1>, <spec-2>, <spec-3>]' --json
     # Or via single-WO / cohort CLI:
     ./bin/pkde workorder dispatch --spec '<inline-json-object-or-array-or-yaml-path>' --json
     # Or via bundled helper script (accepts --specs/--spec/--from, inline JSON object/array or a JSON/YAML path):
     ./.venv/bin/python scripts/dispatch_workorder.py --specs '[<spec-1>, <spec-2>, <spec-3>]'
     # Or via MCP tool:
     # pkde_dispatch_cohort(specs=[{...}, {...}, {...}])
     ```
   - The whole cohort is validated **before anything is created**. If any spec is incomplete, has an unknown role, or has a `depends_on` that matches no earlier `spec_id`/role or existing `WO-NNN`, the result is `status == "INVALID_SPEC"` with per-spec `spec_errors`. Fix the specs and re-dispatch; do not invent placeholder content.
   - On success this atomically:
     1. Creates and commits `WO-NNN-r1` for every spec in the cohort (`pkde workorder create --from <yaml> --commit --json`), resolving intra-cohort `depends_on` aliases (`spec_id`, `role`, or `WO-NNN`).
     2. Partitions the cohort into execution waves based on dependencies and exclusive resource leases (`af3`, `hypex-supervisor`).
     3. Starts **Wave 1** Work Orders immediately (freezes `.pkde/control/contexts/WO-NNN-r1.json`, acquires TTL-bound leases, creates `RUN-NNN`, transitions `queued -> starting -> running` / `in_progress`, and emits `subagent_invocations` ready for parallel `invoke_subagent`).
     4. Places **Wave 2+** Work Orders in `queued` state until Wave 1 prerequisites pass validation or leases are released/expire.
   - Every control-plane transition is checked. `status == "TRANSITION_FAILED"` reports the `failed_step`, the exact `pkde` command, and the CLI error. Surface it; do not proceed as if the work order were running.
3. **Step 2 -- Spin Up Multiple Specialist Subagents in Parallel & Bind `conversation_id`s**:
   - Launch all Wave 1 specialist subagents concurrently in a single `invoke_subagent` call using `dispatch_result["subagent_invocations"]` (each item is a ready `{"TypeName": "pkde-<requested_role>", "Role": "...", "Prompt": <specialist_brief>, ...}`).
   - Record each spawned subagent's `conversation_id` against its Work Order and Run so the control plane and `dashboard.html` track live subagent lineage:
     ```bash
     ./bin/pkde workorder bind-subagent <WO-ID> <conversation_id> [--run-id <RUN-ID>] --json
     # Or via MCP tool: pkde_manage_cohort(action="bind_subagent", work_order_id="<WO-ID>", subagent_id="<conversation_id>", run_id="<RUN-ID>")
     ```
     `--run-id` is optional (defaults to the latest run of the work order) and must belong to that work order. Any binding that cannot be applied is listed in `unmatched` and the call returns `ok: false`.
   - Each `specialist_brief` exports `PKDE_WORK_ORDER_ID`, `PKDE_AGENT_ROLE`, `PKDE_AGENT_SLUG`, and `PKDE_RUN_ID` so concurrent subagents stamp exact Work Order and Run provenance into `.meta.json` sidecars and `.pkde/control/events.ndjson`.
   - Exclusive leases (`af3`, `hypex-supervisor`) expire after `ttl_minutes` (default 60; `PKDE_LEASE_TTL_MINUTES`). Expired leases are released automatically (`lease.expired` event) so a crashed subagent cannot block later waves. Long-running holders renew with `./bin/pkde workorder renew-lease <WO-ID> --json` (MCP: `pkde_manage_cohort(action="renew_lease", work_order_id=...)`).
   - Available specialist roles (`pkde-<role>`): `pkde-computational-biologist`, `pkde-structural-biologist`, `pkde-medicinal-chemist`, `pkde-computational-chemist`, `pkde-admet-dmpk-scientist`, `pkde-experimental-biologist`, `pkde-preclinical-toxicologist`, `pkde-regulatory-scientist`, `pkde-scientific-reviewer`, and the `pkde-hypex-*` tournament cohort (`pkde-hypex-supervisor`, `pkde-hypex-generation`, `pkde-hypex-reflection`, `pkde-hypex-proximity`, `pkde-hypex-tournament`, `pkde-hypex-evolution`, `pkde-hypex-meta-review`).
4. **Step 3 -- 10-Check Mechanical Validation, Correction Loop & Automatic Wave Advancement**:
   - Validate an individual Work Order or validate the entire active cohort at once (which also automatically promotes eligible Wave 2+ queued Work Orders to `running` when their dependencies and leases clear):
     ```bash
     # Validate a single Work Order or all active Work Orders in the cohort:
     ./bin/pkde workorder validate-and-gate all --json
     # Or via MCP tool: pkde_validate_and_gate(work_order_id="all") / pkde_manage_cohort(action="validate_cohort")
     ```
     This runs `pkde validate check <WO-ID> --json` across all 10 checks (`deliverables_exist`, `report_headings`, `paths_resolve`, `provenance_valid`, `analysis_citations`, `relay_coverage`, `version_policy`, `findings_integrity`, `source_tags_resolve`, `unrecognized_json`) plus the non-overridable `deliverables_schema` pre-check, which fails any report-only work order that declares no Layer 0 evidence and is not `synthesis_only`. It then updates the node's validation matrix in `dashboard.html`.
   - If `status == "CORRECTION_REQUIRED"` (mechanical defect, cycle <= 2), send `correction_prompt` back to that specialist subagent (`send_message(Recipient=subagent_id, Message=correction_prompt)`) to fix the defect in-place and re-run `./bin/pkde workorder validate-and-gate <WO-ID> --json`.
   - Newly unblocked Wave 2+ work orders are returned as `promoted_wave["subagent_invocations"]` (cohort/`all` validation) or `next_wave_subagent_invocations` (single work order). Launch them via `invoke_subagent(Subagents=...)` and bind each `conversation_id`. Any `promotion_failures` must be surfaced, not ignored.
   - If `status == "DATA_INTEGRITY_FAILURE"`, halt the run immediately (no retry allowed) and log the escalation in `program-state/decision-log.md`.
   - `status == "VALIDATOR_ERROR"` means the validator itself could not run (no check results). It does **not** consume a correction cycle. Report the `error` and fix the environment or work-order state before re-gating. `ALREADY_VALIDATED` means the work order has already passed the mechanical gate.
5. **Step 4 -- Independent Scientific Review & Layer 2/4 Synthesis**:
   - For mechanically validated work orders (`mechanically_validated`), invoke `pkde-scientific-reviewer` to re-run Phase 2 (`analyze --out raw/reanalysis/<date>-reviewer/`) and write `findings/reviews/<finding>-review.md`.
   - Accept validated work orders via `./bin/pkde workorder accept <WO-ID>`, and update Layer 2 (`program-state/active-series.md`, `liability-tracker.md`, `decision-log.md`, `open-questions.md`) and Layer 4 (`executive/program-summary.md`).
6. **Step 5 -- Final `dashboard.html` Publication**:
   - Run `./bin/pkde dashboard build --standalone --json` so `dashboard.html` reflects the completed multi-agent lineage graph, telemetry history, and all scientific studios.

---

### Mode 3 -- Custom Data Ingestion & Bring-Your-Own-Algorithm (BYOA)

Use **Mode 3** whenever the user supplies proprietary/custom datasets (`.csv`, `.tsv`, `.json`) or custom scoring, ranking, or scientific computation programs (Python scripts, binaries, or container commands). All custom data and algorithms preserve the full PkDE two-phase provenance contract (`raw/<class>/<name>.custom.json` + `.custom.meta.json` + `.custom.analysis.json`). `<class>` must be a registered artifact class (e.g. `bioactivity`, `admet`, `mpo`, `compounds`; see `./bin/pkde artifact classes`).

1. **Two-Phase Custom Data Ingestion (`pkde custom ingest` -> `pkde custom analyze`)**:
   ```bash
   # Phase 1: Ingest a CSV/TSV/JSON dataset into Layer 0 with a SHA-256 provenance sidecar
   ./bin/pkde custom ingest <path/to/data.csv> \
     --class <artifact_class> \
     --name <dataset_slug> \
     --id-col <id_column> \
     --json

   # Phase 2 (offline): classify every record on a numeric metric as PASS/WARN/FAIL
   ./bin/pkde custom analyze raw/<artifact_class>/<dataset_slug>.custom.json \
     --metric <numeric_field> \
     --id-field <id_column> \
     --direction <higher|lower> \
     --pass-cutoff <value> --warn-cutoff <value> \
     [--calibrated] \
     --json
   ```
2. **Two-Phase Custom Algorithm Execution (`pkde custom run` -> `pkde custom analyze`)**:
   - `--cmd` is the command to execute. Use `{input}` and `{output}` placeholders. If you omit them, `--input <path> --output <path>` is appended. The program must write JSON to the output path, or to stdout. Accepted shapes are a list of records or an object with a `records` list. A non-zero exit code, empty output, or invalid JSON fails the run; nothing is fabricated.
   - The SHA-256 digests of the input dataset and of the algorithm file are stamped into `raw/<class>/<name>.custom.meta.json`, and the `custom.external_algorithm_caveat` relay is attached.
   ```bash
   # Phase 1: Execute the user's algorithm in a subprocess (default timeout 300 s)
   ./bin/pkde custom run \
     --cmd "python3 examples/byoa/proprietary_cns_mpo_scorer.py --input {input} --output {output}" \
     --input examples/byoa/sample_private_compounds.json \
     --class mpo \
     --name <run_slug> \
     [--algorithm-id <name@version>] [--timeout 600] \
     --json

   # Phase 2 (offline): evaluate the algorithm output and emit mandatory relays
   ./bin/pkde custom analyze raw/mpo/<run_slug>.custom.json \
     --metric cns_bbb_score \
     --direction higher \
     --pass-cutoff 0.70 --warn-cutoff 0.50 \
     --json
   ```
   - Relays emitted by this path, which must be surfaced verbatim in Layer 1 findings and appear in the dashboard's **Custom Data & BYOA Studio**: `custom.external_algorithm_caveat` (from `run`), `custom.uncalibrated_threshold` (cutoffs not declared `--calibrated`), and `custom.liability_flagged` (one or more records breached the failure cutoff).
3. **Persistent Drop-In Skill & Role Extensions (`extensions/`)**:
   - Place reusable custom skills in `extensions/skills/<skill-name>/SKILL.md` and map them to specialist roles in `extensions/role-grants.yaml`, then run `./.venv/bin/python pkde_plugin/build_targets.py` to compile them into `.agents/plugins/pharmakon-discovery-engine/` and `dist/skill-bundles/`.

---

## Bundled Scripts & References

Available both at the repository root (`./scripts/`, `./references/`) and inside `skills/pharmakon-discovery-engine/`:

- `scripts/start_live_session.py`: Bootstraps a live PkDE session from the user prompt (`--prompt`, optional `--program-name`, `--stage`, `--target`, `--indication`, `--modality`, `--fresh`) and ensures the non-blocking background server on `0.0.0.0:8765` is running.
- `scripts/pkde_runner.py`: Portable CLI wrapper that executes any `pkde` command with automatic environment discovery and dashboard refresh.
- `scripts/dispatch_workorder.py`: CLI helper for single or cohort Work Order dispatch (`--specs`/`--spec`/`--from`, inline JSON object or array, `{"work_orders": [...]}`, or a JSON/YAML path). Equivalent to `./bin/pkde workorder dispatch` / `dispatch-cohort`, and applies the same spec validation.
- `references/role-skill-matrix.md`: Complete mapping of all 22 PkDE roles (`pkde-<role>`) to their categories, domain tools, and injected skill lanes.
- `references/stage0-3-playbook.md`: Stage 0-3 decision gates, degraded-mode offline rules, deliverable templates, and 10-check validation checklist.
