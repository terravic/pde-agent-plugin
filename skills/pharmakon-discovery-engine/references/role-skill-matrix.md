# PDE 22-Role Subagent & Skill Lane Matrix

Every specialist and operational role in `templates/<role>/agent.yaml` compiles into a Markdown Subagent (`.agents/plugins/pharmakon-discovery-engine/agents/pde-<role>.md`) and a packaged skill configuration.

| Subagent (`pde-<role>`) | Category | Primary `pde` CLI Groups | Injected Skill Lanes |
|---|---|---|---|
| `pde-science-program-lead` | Orchestrator | `init`, `doctor`, `triage`, `hypothesis`, `program`, `dashboard` | `pde-dashboard`, `pharmakon-discovery-engine`, `artifact-conventions`, `program-state-management`, `hypothesis-entry`, `stage1-gate-evaluation` |
| `pde-research-operations-controller` | Orchestrator | `workorder`, `run`, `validate`, `relays`, `dashboard`, `site` | `pde-dashboard`, `pharmakon-discovery-engine`, `artifact-conventions`, `site-generation` |
| `pde-head-of-discovery` | Advisory | `program`, `triage`, `dossier`, `dashboard` | `artifact-conventions` |
| `pde-bootstrapper` | Operations | `init`, `doctor`, `env`, `tools`, `schema` | `pharmakon-discovery-engine`, `artifact-conventions` |
| `pde-finding-validator` | Quality Gate | `validate`, `relays`, `workorder` | `artifact-conventions` |
| `pde-scientific-reviewer` | Quality Gate | `* analyze --out raw/reanalysis/...`, `validate` | `citation-resolution`, `tournament-corpus`, `citation-verification`, `artifact-conventions` |
| `pde-project-curator` | Presentation | `dashboard`, `site`, `dossier` | `artifact-conventions`, `site-generation`, `pde-dashboard` |
| `pde-structural-biologist` | Specialist | `alphafold`, `structure`, `pocket`, `ppi`, `conservation`, `homology` | `protein-structure-confidence`, `pocket-druggability`, `binding-mode-analysis`, `artifact-conventions` |
| `pde-computational-biologist` | Specialist | `genetics`, `gwas`, `alphagenome`, `expression`, `gtex`, `cellxgene`, `geo`, `allen`, `phenotype`, `pathway` | `regulatory-variant-effect`, `tournament-corpus`, `target-genetic-evidence`, `tissue-expression-profile`, `artifact-conventions` |
| `pde-medicinal-chemist` | Specialist | `compound`, `analog`, `similar`, `mmp`, `mpo`, `retro`, `pubchem` | `compound-property-profile`, `admet-property-prediction`, `sar-series-analysis`, `structure-similarity-search`, `artifact-conventions` |
| `pde-computational-chemist` | Specialist | `docking`, `screen`, `structure_screen`, `pocket`, `compound` | `protein-structure-confidence`, `pocket-druggability`, `compound-property-profile`, `binding-mode-analysis`, `sar-series-analysis`, `structure-similarity-search`, `artifact-conventions` |
| `pde-admet-dmpk-scientist` | Specialist | `admet`, `pk`, `compound` | `compound-property-profile`, `admet-property-prediction`, `bioactivity-landscape`, `in-vivo-pk-analysis`, `structure-similarity-search`, `artifact-conventions` |
| `pde-experimental-biologist` | Specialist | `assay`, `selectivity`, `pk` | `citation-resolution`, `bioactivity-landscape`, `in-vivo-pk-analysis`, `artifact-conventions` |
| `pde-preclinical-toxicologist` | Specialist | `tox`, `admet`, `genetics`, `expression` | `tissue-expression-profile`, `target-genetic-evidence`, `preclinical-safety-assessment`, `compound-property-profile`, `admet-property-prediction`, `in-vivo-pk-analysis`, `artifact-conventions` |
| `pde-regulatory-scientist` | Specialist | `faers`, `trials`, `patent`, `differentiation`, `manufacturing`, `dossier` | `citation-resolution`, `preclinical-safety-assessment`, `in-vivo-pk-analysis`, `compound-property-profile`, `artifact-conventions` |
| `pde-hypex-supervisor` | Hypex Graph | `coscientist`, `hypex` | `artifact-conventions`, `hypothesis-run-corpus`, `run-protocol`, `hypex-tool-setup` |
| `pde-hypex-generation` | Hypex Graph | `hypex`, `coscientist` | `artifact-conventions`, `literature-search`, `citation-resolution`, `citation-verification`, `hypothesis-schema`, `debate-protocol`, `hypex-tool-setup` |
| `pde-hypex-reflection` | Hypex Graph | `hypex`, `coscientist` | `artifact-conventions`, `literature-search`, `citation-resolution`, `citation-verification`, `review-rubric`, `safety-screen`, `hypex-tool-setup` |
| `pde-hypex-proximity` | Hypex Graph | `hypex`, `coscientist` | `artifact-conventions`, `proximity-protocol`, `hypex-tool-setup` |
| `pde-hypex-tournament` | Hypex Graph | `hypex`, `coscientist` | `artifact-conventions`, `elo-tournament`, `debate-protocol`, `review-rubric`, `hypex-tool-setup` |
| `pde-hypex-evolution` | Hypex Graph | `hypex`, `coscientist` | `artifact-conventions`, `literature-search`, `citation-resolution`, `citation-verification`, `evolution-operators`, `hypothesis-schema`, `hypex-tool-setup` |
| `pde-hypex-meta-review` | Hypex Graph | `hypex`, `coscientist` | `artifact-conventions`, `literature-search`, `citation-resolution`, `citation-verification`, `meta-review-protocol`, `hypex-tool-setup` |
