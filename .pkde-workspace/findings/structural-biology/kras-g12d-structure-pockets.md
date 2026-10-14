# KRAS G12D Structure Confidence & Switch-II Pocket Druggability (WO-002-r1)

## Summary
Completed structural confidence and pocket druggability evaluation for `WO-002-r1`. The KRAS G12D catalytic domain shows mean pLDDT of 91.4 {source: raw/structures/KRAS_G12D.afdb.json $.mean_plddt} and mean PAE of 3.18 {source: raw/structures/KRAS_G12D.pae.json $.mean_pae} A.

## Key Findings
- **Switch-II Loop Plasticity**: Switch-II residues 58-72 exhibit mean pLDDT of 88.6 {source: raw/structures/KRAS_G12D.afdb.json $.switch_ii_mean_plddt}.
- **Switch-II Allosteric Pocket (SII-P)**: `POCKET_1_SIIP` achieves a druggability score of 0.84 {source: raw/pocket/KRAS_G12D_SIIP.pockets.json $.top_druggability_score} with volume 542.6 {source: raw/pocket/KRAS_G12D_SIIP.pockets.json $.pockets[0].volume_a3} A^3.
- **Relay: `SWITCH_II_CONFORMATIONAL_PLASTICITY`** — Use ensemble docking across Switch-II loop states.
- **Relay: `ASP12_SALT_BRIDGE_ANCHOR_REQUIRED`** — Anchor basic amine against Asp12 carboxylate.

## Verdict
**PASS** — Switch-II pocket is structurally validated for non-covalent salt-bridge inhibitor design.

## Evidence
- [KRAS G12D pLDDT Profile](../../raw/structures/KRAS_G12D.afdb.json)
- [KRAS G12D PAE Matrix](../../raw/structures/KRAS_G12D.pae.json)
- [Switch-II Pocket Druggability](../../raw/pocket/KRAS_G12D_SIIP.pockets.json)

## Implications
Prioritize pyrido[4,3-d]pyrimidine scaffolds projecting a (1R,5S)-3,8-diazabicyclo[3.2.1]octane warhead toward Asp12.
