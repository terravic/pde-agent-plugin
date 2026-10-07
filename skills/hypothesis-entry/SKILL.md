---
name: hypothesis-entry
description: "Hypothesis entry: how hypotheses enter a PDE science program. Four strategies exist, each producing a Layer 0 artifact under raw/hypotheses/ with its own schema and threshold set. Use this skill when planning or executing hypothesis entry -- deciding which strategy to use, running the adopt command, or interpreting the assessment output. Hypothesis entry feeds into Stage 0 bounded portfolio triage (see science-program-lead template Section 5a). Do not use this skill for downstream analysis of hypotheses (stage 1+), for reading co-scientist tournament details (use tournament-corpus), or for running a hypex tournament (use the hypex work-order path)."
---

## 1. The four strategies

| Strategy | Command | Layer 0 schema | Availability |
|---|---|---|---|
| **Sponsor** | `pde hypothesis adopt --origin sponsor` | `pde.hypothesis-set.v1` | Always available |
| **Charter** | `pde hypothesis adopt --origin charter` | `pde.hypothesis-set.v1` | Always available |
| **Co-Scientist** | `pde coscientist ingest` | `pde.coscientist.v1` | Requires a Co-Scientist export file |
| **Hypex** | `hypex-supervisor` work order, then `pde hypex ingest` | `pde.hypex.v1` | Requires PDE-provisioned Hypex tools, templates, and supervisor lease |

Each strategy writes its own vendor-native Layer 0 artifact. The shared
contract is `pde.hypothesis-assessment.v1`, emitted by each strategy's
`analyze` command. **There is no single score comparable across
strategies.** `score` is an object carrying `{value, basis}` or `null`;
cross-strategy comparison is a judgement the program lead makes in prose.

## 2. When to prefer each strategy

| If the starting material is... | Use | Why |
|---|---|---|
| A sponsor-supplied list of hypotheses | `pde hypothesis adopt --origin sponsor` | Honest provenance; attestation recorded |
| Hypotheses authored in the program charter | `pde hypothesis adopt --origin charter` | Same mechanism, charter-specific infix |
| A Co-Scientist tournament export | `pde coscientist ingest` | Existing validated pipeline with ELO ranking |
| A need for adversarial hypothesis exploration | `hypex-supervisor` work order | Multi-epoch tournament with review panel, proximity, and evolution |
| A published hypothesis set (paper, prior program) | `pde hypothesis adopt --origin publication` or `--origin prior-program` | Requires `--cite` for the source reference |

## 3. Tool invocations

### Adoption (sponsor, charter, prior-program, publication)

```bash
# Phase 1: adopt the hypothesis set
pde hypothesis adopt hypotheses.json \
  --origin sponsor \
  --attest "Provided by Dr. Smith on 2026-09-01 as starting material for the CDK4 program" \
  [--cite DOI:10.1234/example]

# Phase 2: assess the adopted set
pde hypothesis analyze raw/hypotheses/<slug>.adopted.json
```

### Co-Scientist (unchanged)

```bash
pde coscientist ingest export.json [--top N]
pde coscientist analyze raw/hypotheses/cs-<session>.tournament.json
```

## 4. Mandatory relays

| Relay code | Kind | Fires when | Obligation |
|---|---|---|---|
| `hypothesis.adopted_not_generated` | Qualifier | Every adoption | Quote the attestation verbatim in any finding that rests on this artifact. Do not describe the set as PDE-derived. |
| `hypothesis.unranked_set` | Qualifier | Every adopted set analysis | Array position is input order, not preference. Do not present as a leaderboard. |

## 5. The no-silent-substitution rule

**If the sponsor named a strategy and `pde doctor` reports it unavailable,
the lead reports blocked. It does NOT silently substitute another.**

A substituted strategy produces a differently-shaped artifact with a
different score basis. A silent substitution is a provenance error that
surfaces much later, when a finding cites an artifact whose shape does
not match what the sponsor expected.

Check availability:

```bash
pde doctor --json | jq '.checks[] | select(.name | startswith("hypothesis strategy"))'
```

## 6. Threshold sets

| Strategy | Threshold set | Quality thresholds? |
|---|---|---|
| Adopted (sponsor, charter, prior-program, publication) | `hypothesis-set@1.0` | No — structural only (`min_candidates`) |
| Co-Scientist | `coscientist@1.1` | Yes — ELO gap, win rate, contradiction count |
| Hypex | `hypex@1.0` | Yes — but three values ship UNRESOLVED |

## 7. Assessment output

Every strategy's `analyze` emits the shared `pde.hypothesis-assessment.v1`
core:

```json
{
  "schema": "pde.hypothesis-assessment.v1",
  "strategy": "adopted | coscientist | hypex",
  "source_artifact": "raw/hypotheses/...",
  "source_sha256": "...",
  "candidates": [
    {
      "candidate_id": "...",
      "statement": "...",
      "rank": null,
      "score": null,
      "origin": "adopted | generated"
    }
  ]
}
```

For adopted sets: `rank` is always `null`, `score` is always `null`.
For ranked strategies: `score` is `{value: <number>, basis: "<set>"}` —
never a bare number.
