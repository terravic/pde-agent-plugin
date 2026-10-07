# Co-Scientist / Hypex Hypothesis Tournament Report (WO-005-r1)

## Summary
Executed a 24-match WO-005-r1 Co-Scientist / Hypex ELO tournament across 4 {source: raw/hypotheses/kras_resistance.tournament.json $.n_hypotheses} competing hypotheses. `HYP-001` achieved the #1 tournament ELO rating of 1648 {source: raw/hypotheses/kras_resistance.tournament.json $.top_elo} (11-1 record, win rate 0.917 {source: raw/hypotheses/kras_resistance.tournament.json $.hypotheses[0].win_rate}).

## Key Findings
- **#1 Ranked Hypothesis (`HYP-001`, ELO 1648)**: Pulsatile MRTX1133 + SHP2 co-inhibition suppresses RTK-driven WT RAS feedback.
- **#2 Ranked Hypothesis (`HYP-002`, ELO 1572 {source: raw/hypotheses/kras_resistance.tournament.json $.hypotheses[1].elo})**: Conformational C2-pyrrolizidine lock retains potency against Tyr96Asp/His95Gln Switch-II mutations.
- **Relay: `HYPEX_TOP_RANKED_SHP2_COMBO`** — Prioritize AsPC-1 72h pERK rebound combination matrix in Stage 3.

## Verdict
**PASS** — Tournament converged with clear separation (ELO 1648 vs 1572) and actionable experimental relays.

## Evidence
- [Hypex Tournament Leaderboard](../../raw/hypotheses/kras_resistance.tournament.json)

## Implications
Advance `HYP-001` (combination biology) and `HYP-002`/`HYP-003` (Cycle 2 chemistry) into Stage 3 nominations.
