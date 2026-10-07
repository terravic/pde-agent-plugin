---
name: proprietary-cns-scorer
description: "Run the user-supplied CNS Blood-Brain Barrier and efflux multiparameter optimization algorithm via pde custom run and evaluate candidates offline via pde custom analyze."
metadata:
  display_name: "Proprietary CNS BBB & Efflux Scorer (BYOA Example)"
---

# Proprietary CNS BBB & Efflux Scorer (`proprietary-cns-scorer`)

## When to Use

Use this skill when evaluating internal CNS candidate series with measured or predicted brain-to-plasma partition (`kp_uu_brain`), P-gp/BCRP efflux ratios (`mdck_er`), and physicochemical properties using the proprietary CNS BBB scoring algorithm (`examples/byoa/proprietary_cns_mpo_scorer.py`).

## Tool Execution Contract (Two-Phase Invariant)

Every invocation MUST follow the two-phase execution invariant:

### Phase 1: Execute Proprietary Algorithm (`pde custom run`)

```bash
pde custom run \
  --cmd "python3 examples/byoa/proprietary_cns_mpo_scorer.py --input {input} --output {output}" \
  --input examples/byoa/sample_private_compounds.json \
  --class mpo \
  --name cns-lead-series \
  --algorithm-id "proprietary-cns-bbb-mpo@1.2.0"
```

Produces:
- `raw/mpo/cns-lead-series.custom.json`
- `raw/mpo/cns-lead-series.custom.meta.json` (contains `source_sha256` and `algorithm_sha256`)

### Phase 2: Offline Thresholded Evaluation (`pde custom analyze`)

Immediately run Phase 2 offline analysis before calling any other tool:

```bash
pde custom analyze raw/mpo/cns-lead-series.custom.json \
  --metric cns_bbb_score \
  --id-field compound_id \
  --pass-cutoff 0.70 \
  --warn-cutoff 0.40 \
  --direction higher
```

Produces:
- `raw/mpo/cns-lead-series.custom.analysis.json`

## Mandatory Relays & Provenance Citations

When writing a Layer 1 finding in `findings/`, you MUST:
1. Surface every code present in `mandatory_relays` of `cns-lead-series.custom.analysis.json` verbatim:
   - `**Relay: \`custom.external_algorithm_caveat\`**`
   - `**Relay: \`custom.uncalibrated_threshold\`**` (when uncalibrated cutoffs are used)
   - `**Relay: \`custom.liability_flagged\`**` (when one or more candidates classify as `FAIL`)
2. Cite the exact JSON paths for all quantitative claims, for example:
   - `{source: raw/mpo/cns-lead-series.custom.analysis.json#$.metrics.max}`
   - `{source: raw/mpo/cns-lead-series.custom.analysis.json#$.assessment.top_candidate}`
