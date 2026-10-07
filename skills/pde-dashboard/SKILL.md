---
name: pde-dashboard
description: "Builds and renders the single-pane interactive PDE Scientific Dashboard combining the multi-agent lineage graph, validation scorecard, and inter-agent message stream with PDE's 14 interactive scientific viewers (3Dmol.js structures/docking, Plotly ADMET radar, pLDDT/PAE, gnomAD, GTEx, and Hypex ELO tournaments)."
metadata:
  display_name: PDE Unified Mission Control & Interactive Scientific Dashboard
---

# PDE Unified Mission Control & Interactive Scientific Dashboard (`pde-dashboard`)

Use this skill whenever you need to build, update, or serve the unified **Multi-Agent + PDE Interactive Scientific Dashboard** (`dashboard.html`).

## What the Dashboard Renders

1. **Pane 1 — Multi-Agent Operations**:
   - **Interactive SVG Agent Lineage Forest**: Hierarchical layout (`NODE_W=180`, `NODE_H=76`) with vertical/horizontal orientation transpose (`t`), zoom/pan, fit-to-screen (`f`), bezier state edges, and pulse animations on active agents.
   - **Agent & Work-Order Inspector Drawer**: Clicking any agent node displays its Work Order metadata (`WO-NNN-rM`, stage, cycle, attempt counter), **Injected Skills pills** (from `templates/<role>/agent.yaml`), and the **10-Check Mechanical Validation Matrix** (`deliverables_exist`, `report_headings`, `paths_resolve`, `provenance_valid`, `analysis_citations`, `relay_coverage`, `version_policy`, `findings_integrity`, `source_tags_resolve`, `unrecognized_json`).
   - **Resource Leases & Inter-Agent Event Stream**: Live tracker for `.pde/control/leases/*.json` (`af3`, `hypex-supervisor`) and filterable `.pde/control/events.ndjson` message log.
2. **Pane 2 — PDE Scientific Output & 14 Embedded Interactive Viewers**:
   - **Overview, Stage Gates & Mandatory Relays**: Stage 0–3 Triage Scorecard, Liability Tracker table, and Mandatory Relays audit matrix.
   - **Specialist Findings & Dossier Reader (Layer 1)**: Discipline-grouped Markdown/KaTeX reports with interactive `{source: ...}` verification badges and `**Relay: ...**` callouts.
   - **14 Interactive Scientific Viewers Studio (Layer 0 + Analysis)**:
     - `3Dmol.js` 3D Structure (`.cif`/`.pdb` colored by AlphaFold pLDDT bands), Pocket Druggability (`.pockets.json`), 3D Molecule SDF (`.3d.sdf`), and Docking Poses (`.receptor.pdbqt` + `.poses.pdbqt`).
     - `Plotly.js` 5-Axis ADMET Radar (`.predict.json`), pLDDT Confidence Line Plot (`.afdb.json`), 2D PAE Heatmap (`.pae.json`), gnomAD Constraint Gauges (`.gnomad-constraint.json`), and GTEx Tissue Expression Bars (`.tissue.json`).
     - BRICS Fragment & SAR Studio (`.brics.json`), Docking Pose Score Comparison (`.docking_result.json`), Contact Map (`.contacts.json`), Hypothesis ELO Tournament Studio (`.tournament.json` / `.hypex.json`), and the 3-File Provenance Inspector (`Layer 0` + `.meta.json` + `.analysis.json`).

## Usage

### 1. Build Self-Contained Standalone Snapshot (`dashboard.html`)
```bash
python3 skills/pde-dashboard/scripts/render_dashboard.py
# Or directly via the pde CLI:
./bin/pde dashboard build --standalone --json
```

### 2. Serve Live Auto-Refreshing Dashboard (`SSE /api/stream`)
```bash
./bin/pde dashboard serve --port 8765
```
