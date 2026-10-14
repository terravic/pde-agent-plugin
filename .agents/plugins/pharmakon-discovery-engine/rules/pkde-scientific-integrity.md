---
name: pkde-scientific-integrity
description: "Mandatory scientific integrity, two-phase tool execution, provenance sidecars, and relay rules for PkDE."
trigger: always_on
---

# PkDE Scientific Integrity & Provenance Rules

1. **Two-Phase Execution Invariant**: Every `pkde` domain tool command (Phase 1: `fetch`/`run`/`compute`/`predict`) MUST be followed immediately by its corresponding `pkde <tool> analyze` (Phase 2) command before running any other tool.
2. **Never Hand-Craft Layer 0 JSON**: All files in `raw/` must be produced by `pkde` CLI commands with matching `.meta.json` SHA-256 provenance sidecars and `.analysis.json` interpretation records.
3. **Mandatory Relays & Inline Source Citations**: Every code in `mandatory_relays` from `.analysis.json` must be surfaced verbatim in Layer 1 Markdown reports (`**Relay: \`<code>\`**`), and every quantitative claim must cite its Layer 0 JSON path (`{source: raw/<category>/<file>#$.path}`).
4. **Always Update the Interactive Dashboard**: After completing a scientific query or Work Order cycle, run `./bin/pkde dashboard build --standalone` (or `pkde_render_dashboard`) so `dashboard.html` reflects the latest multi-agent lineage graph and 14 scientific viewers.
