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
   Always source `bin/env.sh` from the repository root (or invoke commands via `pde_exec` / `scripts/pde_runner.py`):
   ```bash
   source "${PDE_ROOT:-$(git rev-parse --show-toplevel)}/bin/env.sh"
   ```
2. **Mandatory Two-Phase Scientific Execution**:
   Every PDE domain command group (`genetics`, `gwas`, `alphagenome`, `expression`, `gtex`, `cellxgene`, `geo`, `allen`, `phenotype`, `pathway`, `alphafold`, `structure`, `pocket`, `ppi`, `conservation`, `homology`, `compound`, `analog`, `similar`, `mmp`, `mpo`, `retro`, `pubchem`, `docking`, `screen`, `structure_screen`, `admet`, `pk`, `assay`, `selectivity`, `tox`, `faers`, `trials`, `patent`, `differentiation`, `manufacturing`, `coscientist`, `hypex`, `hypothesis`) operates in two strict phases:
   - **Phase 1 (`fetch` / `run` / `compute` / `search` / `predict` / `generate`)**: Produces immutable **Layer 0** raw data (`raw/<category>/<stem>.<ext>`) and a cryptographic SHA-256 provenance sidecar (`<stem>.meta.json`).
   - **Phase 2 (`analyze`)**: Evaluates Phase 1 outputs against domain thresholds in `tools/pde/thresholds/<domain>.yaml` and writes `<stem>.analysis.json` containing `verdict`, `summary`, `thresholds_applied`, and `mandatory_relays`.
   - **Enforcement**: Running any subsequent command without completing Phase 2 (`analyze`) is blocked by `enforce_phase_two`.
3. **Mandatory Relays & Inline Source Provenance**:
   Every entry in `mandatory_relays` inside `<stem>.analysis.json` **must** appear verbatim in the corresponding Layer 1 Markdown report (`findings/<discipline>/<topic>.md`) as `**Relay: \`<code>\`**`, and every quantitative claim must carry an inline `{source: raw/<category>/<file>#$.json.path}` citation.
4. **Live Auto-Populating `dashboard.html` (Unified Interactive Scientific Dashboard)**:
   - As soon as the skill starts executing (`pde init`, `pde doctor --json`, or `pde_dispatch_workorder`), `dashboard.html` is automatically created in both the active workspace (`$PDE_PROJECT/dashboard.html`) and the repository root (`dashboard.html`).
   - Every time the skill or any spawned specialist subagent runs a CLI command, dispatches a work order, writes a Layer 0/Layer 1 artifact, or executes a validation gate, `dashboard.html` is automatically rebuilt in place so the **Multi-Agent Lineage Graph + 10-Check Validation Matrix** and **PDE's 14 Embedded Scientific Viewers** populate live as work progresses.

---

## Execution Modes

### Mode 1 — Interactive Scientific Q&A ("Fast-Path PDE Questions")

Use **Mode 1** when the user asks a focused, single-domain scientific question about a target, gene, protein structure, compound SMILES, SAR series, ADMET liability, or Stage 0 triage scorecard.

1. **Capability Check & Initial `dashboard.html` Creation**:
   Run `pde doctor --json` (via `pde_exec("doctor --json")` or `./bin/pde doctor --json`) to confirm available APIs and local tools and immediately initialize `dashboard.html`.
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
   Every CLI execution automatically refreshes `dashboard.html`; you may also call `pde_render_dashboard()` (or `./bin/pde dashboard build --standalone --json`) at the end of the turn to confirm the final snapshot.

---

### Mode 2 — Full Multi-Agent Program / Cohort Mode

Use **Mode 2** whenever the scientific task spans multiple disciplines (e.g., target genetics + 3D structure/pockets + medicinal chemistry/ADMET + molecular docking + preclinical safety, or a multi-agent Hypex tournament). In this mode, the skill acts as the **Science Program Lead & Research Operations Controller** and spins up multiple specialist subagents in parallel:

1. **Step 1 — Charter, Layer 2 Initialization & Initial `dashboard.html`**:
   - Initialize `$PDE_PROJECT` (`./bin/pde init <program-dir>`), run `./bin/pde doctor --json` to build the capability exclusion map, and record the program charter in `program-state/decision-log.md` (`DEC-001`). This immediately creates `dashboard.html` with the root orchestrator nodes.
2. **Step 2 — Atomic Work-Order Dispatch (Populates Running Agent Nodes in `dashboard.html`)**:
   - For each specialist discipline needed for the scientific task, call `pde_dispatch_workorder(spec)` (or run `python3 skills/pharmakon-discovery-engine/scripts/dispatch_workorder.py --spec <spec.json>`).
   - This atomically:
     1. Creates and commits `WO-NNN-r1` (`pde workorder create --from <yaml> --commit --json`).
     2. Freezes the checksummed context snapshot in `.pde/control/contexts/WO-NNN-r1.json`.
     3. Acquires any required resource lease in `.pde/control/leases/<resource_class>.json` (`af3`, `hypex-supervisor`).
     4. Creates `RUN-NNN`, transitions `queued -> starting -> running` (`in_progress`), and immediately updates `dashboard.html` so each dispatched specialist appears as an active `running` node in the Multi-Agent Lineage Graph.
3. **Step 3 — Spin Up Multiple Specialist Subagents in Parallel**:
   - Launch all dispatched specialist subagents concurrently in a single `invoke_subagent` call (`Subagents=[{"TypeName": "pde-<requested_role>", "Role": "...", "Prompt": dispatch_result["specialist_brief"]}, ...]`).
   - Available specialist roles (`pde-<role>`): `pde-computational-biologist`, `pde-structural-biologist`, `pde-medicinal-chemist`, `pde-computational-chemist`, `pde-admet-dmpk-scientist`, `pde-experimental-biologist`, `pde-preclinical-toxicologist`, `pde-regulatory-scientist`, `pde-scientific-reviewer`, and the `pde-hypex-*` tournament cohort (`pde-hypex-supervisor`, `pde-hypex-generation`, `pde-hypex-reflection`, `pde-hypex-proximity`, `pde-hypex-tournament`, `pde-hypex-evolution`, `pde-hypex-meta-review`).
   - As each subagent executes its Phase 1 and Phase 2 `pde` CLI commands and writes its Layer 1 finding (`findings/<discipline>/<slug>.md`), `dashboard.html` updates automatically with the new scientific artifacts and viewers.
4. **Step 4 — 10-Check Mechanical Validation & Correction Loop**:
   - When each specialist subagent finishes, call `pde_validate_and_gate(work_order_id, run_id)` (which runs `pde validate check <WO-ID> --json` across all 10 checks: `deliverables_exist`, `report_headings`, `paths_resolve`, `provenance_valid`, `analysis_citations`, `relay_coverage`, `version_policy`, `findings_integrity`, `source_tags_resolve`, `unrecognized_json` and updates the node's validation matrix in `dashboard.html`).
   - If `status == "CORRECTION_REQUIRED"` (mechanical defect, cycle <= 2), send `correction_prompt` back to that specialist subagent (`send_message(Recipient=subagent_id, Message=correction_prompt)`) to fix the defect in-place and re-run `pde_validate_and_gate`.
   - If `status == "DATA_INTEGRITY_FAILURE"`, halt the run immediately (no retry allowed) and log the escalation in `program-state/decision-log.md`.
5. **Step 5 — Independent Scientific Review & Layer 2/4 Synthesis**:
   - For mechanically validated work orders (`mechanically_validated`), invoke `pde-scientific-reviewer` to re-run Phase 2 (`analyze --out raw/reanalysis/<date>-reviewer/`) and write `findings/reviews/<finding>-review.md`.
   - Accept validated work orders via `pde workorder accept <WO-ID>`, and update Layer 2 (`program-state/active-series.md`, `liability-tracker.md`, `decision-log.md`, `open-questions.md`) and Layer 4 (`executive/program-summary.md`).
6. **Step 6 — Final `dashboard.html` Publication**:
   - Run `pde dashboard build --standalone` (and `pde dashboard serve --port 8765` if live SSE streaming in a browser is desired) so `dashboard.html` reflects the completed multi-agent lineage graph and all 14 scientific viewers.

---

## Bundled Scripts & References

- `scripts/pde_runner.py`: Portable CLI wrapper that executes any `pde` command with automatic environment discovery and dashboard refresh.
- `scripts/dispatch_workorder.py`: CLI helper for atomic Work Order intake, snapshot creation, lease check, and specialist brief generation.
- `references/role-skill-matrix.md`: Complete mapping of all 22 PDE roles (`pde-<role>`) to their categories, domain tools, and injected skill lanes.
- `references/stage0-3-playbook.md`: Stage 0–3 decision gates, deliverable templates, and 10-check validation checklist.
