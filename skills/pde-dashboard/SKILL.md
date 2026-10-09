---
name: pde-dashboard
description: "Builds and renders the single-pane interactive PDE Scientific Dashboard combining the multi-agent lineage graph, validation scorecard, and inter-agent message stream with PDE's 14 interactive scientific viewers (3Dmol.js structures/docking, Plotly ADMET radar, pLDDT/PAE, gnomAD, GTEx, and Hypex ELO tournaments)."
metadata:
  display_name: PDE Unified Mission Control & Interactive Scientific Dashboard
---

# PDE Unified Mission Control & Interactive Scientific Dashboard (`pde-dashboard`)

Use this skill whenever you need to build, update, or serve the unified **Multi-Agent + PDE Interactive Scientific Dashboard** (`dashboard.html`) or start the non-blocking background HTTP/SSE server (`0.0.0.0:8765`).

## What the Dashboard Renders

1. **Pane 1 -- Multi-Agent Operations (`Split` & `Agents` Views)**:
   - **Interactive SVG Agent Lineage Forest**: Hierarchical layout (`NODE_W=180`, `NODE_H=76`) with vertical/horizontal orientation transpose (`t`), zoom/pan, fit-to-screen (`f`), bezier state edges, and pulse animations on active agents.
   - **Agent & Work-Order Inspector Drawer**: Clicking any agent node displays its Work Order metadata (`WO-NNN-rM`, stage, cycle, attempt counter), **Injected Skills pills** (from `templates/<role>/agent.yaml`), **Recent Agent Communications**, and the **10-Check Mechanical Validation Matrix** (`deliverables_exist`, `report_headings`, `paths_resolve`, `provenance_valid`, `analysis_citations`, `relay_coverage`, `version_policy`, `findings_integrity`, `source_tags_resolve`, `unrecognized_json`).
   - **Resource Leases & Inter-Agent Event Stream**: Live tracker for `.pde/control/leases/*.json` (`af3`, `hypex-supervisor`) and filterable `.pde/control/events.ndjson` message log.
2. **Pane 2 -- PDE Scientific Output & Embedded Interactive Viewers (`Split` & `Discovery` Views)**:
   - **Overview, Session Prompt Charter, Stage Gates & Mandatory Relays**: Active Session Prompt Charter (`.pde/program.yaml`), Stage 0-4 Triage Scorecard, Liability Tracker table, and Mandatory Relays audit matrix.
   - **Specialist Findings & Dossier Reader (Layer 1)**: Discipline-grouped Markdown/KaTeX reports with interactive `{source: ...}` verification badges and `**Relay: ...**` callouts.
   - **Interactive Scientific Viewers Studio (Layer 0 + Analysis)**:
     - `3Dmol.js` 3D Structure (`.cif`/`.pdb` colored by AlphaFold pLDDT bands), Pocket Druggability (`.pockets.json`), 3D Molecule SDF (`.3d.sdf`), and Docking Poses (`.receptor.pdbqt` + `.poses.pdbqt`).
     - `Plotly.js` 5-Axis ADMET Radar (`.predict.json`), pLDDT Confidence Line Plot (`.afdb.json`), 2D PAE Heatmap (`.pae.json`), gnomAD Constraint Gauges (`.gnomad-constraint.json`), and GTEx Tissue Expression Bars (`.tissue.json`).
     - BRICS Fragment & SAR Studio (`.brics.json`), Docking Pose Score Comparison (`.docking_result.json`), Contact Map (`.contacts.json`), Hypothesis ELO Tournament Studio (`.tournament.json` / `.hypex.json`), and the 3-File Provenance Inspector (`Layer 0` + `.meta.json` + `.analysis.json`).
3. **Live Telemetry Console (`#telemetry-drawer` + 4th `Telemetry` Full-Screen View)**:
   - **Persistent Collapsible Bottom Console (`#telemetry-drawer`)**: Anchored across `Split`, `Agents`, and `Discovery` views with `Ticker` (`38px`), `Console` (`205px`), and `Full View` toggles, category filter pills, text search, and hover/scroll auto-pause.
   - **4th Full-Screen `Telemetry` View (`#telemetry-view`)**: Dedicated two-column Mission Telemetry Terminal + Live Active Agents & Recent Discovery Additions status board.
   - **One-Click Deep Navigation**: Clicking any telemetry one-liner automatically opens the corresponding pane and selects the exact Agent node, Layer 1 Finding, Layer 0 Scientific Studio viewer, or Mandatory Relay table.
   - **Non-Blocking Differential DOM Updates**: Per-section signatures and `requestAnimationFrame` coalescing ensure active `3Dmol.js` WebGL cameras, `Plotly.js` charts, Findings reader scroll positions, and SVG pan/zoom states never reset while live telemetry streams in.

## Usage

### 1. Start Non-Blocking Background Server from Prompt (`0.0.0.0:8765`)
```bash
./bin/pde dashboard start --prompt "<user prompt>" --host 0.0.0.0 --port 8765 --json
./bin/pde dashboard status --json
./bin/pde dashboard stop --json
```

### 2. Build Self-Contained Standalone Snapshot (`dashboard.html`)
```bash
python3 skills/pde-dashboard/scripts/render_dashboard.py
# Or directly via the pde CLI:
./bin/pde dashboard build --standalone --json
```

### 3. Serve Foreground Auto-Refreshing Dashboard (`SSE /api/stream`)
```bash
./bin/pde dashboard serve --host 0.0.0.0 --port 8765
```
