# Privacy Notice

> **DRAFT -- REQUIRES LEGAL REVIEW**  
> This document is a template generated for technical review and does not constitute legal advice. Replace all bracketed placeholders (`[PLACEHOLDER]`) and obtain formal review by qualified legal counsel before publication or operational reliance.

**Controller / Operator:** `[ORGANIZATION_NAME]`  
**Contact Email:** `[PRIVACY_CONTACT_EMAIL]`  
**Data Protection Officer (if applicable):** `[DPO_NAME_AND_EMAIL]`  
**Effective Date:** `[EFFECTIVE_DATE]`  
**Primary Operating Region:** `[DECLARED_DATA_RESIDENCY_REGION]`

---

## 1. Scope and Execution Architecture

`pkde-agent-plugin` executes locally as a command-line engine (`bin/pkde`), Model Context Protocol (MCP) stdio server (`bin/pkde-mcp`), and local interactive HTML dashboard (`dashboard.html`, served on `127.0.0.1:8765` by default).

- The plugin does **not** operate a multi-tenant user database, user account registry, telemetry SaaS backend, or analytics tracker.
- The plugin's own code makes **zero** direct calls to LLM provider APIs; LLM inference is governed solely by the user's host agent harness configuration (`[HOST_AGENT_HARNESS_PROVIDER]`, region: `[HOST_LLM_REGION]`).
- All Layer 0 artifacts, provenance sidecars, findings, and dashboards are written locally inside the user's workspace directory (`.pkde-workspace/` or `--project <dir>`).

## 2. Categories of Data Processed

| Data Category | Storage Location | Retention Policy | Notes |
|---|---|---|---|
| Scientific queries, gene symbols, compound SMILES, and local workspace files | Local filesystem (`.pkde-workspace/` or `--project`) | User-controlled (`[RETENTION_PERIOD]`); deleted directly via filesystem removal | Users should avoid submitting unredacted personal data (PII) or Protected Health Information (PHI) into public API lookup commands. |
| Command audit events & cryptographic hashes | Local `.pkde/control/events.ndjson` and `.meta.json` | User-controlled (`[RETENTION_PERIOD]`) | Records tool names, SHA-256 digests, and timestamps locally. |
| Outbound HTTP request metadata (source IP address, User-Agent `pkde-cli/1.0`) | Transmitted to third-party public scientific APIs when Phase 1 online commands run | Governed by each respective third-party API operator | IP addresses may constitute personal data under applicable privacy regulations (e.g., GDPR). Set `PKDE_OFFLINE=1` to prevent outbound network calls. |

## 3. Optional Third-Party Data Processors and External Scientific APIs

No third-party requests are made on dashboard render (`dashboard.html` and static viewers run strictly offline with zero CDN or external font requests). When a user explicitly executes Phase 1 online `pkde` retrieval commands, outbound HTTPS requests may be sent to the following external services:

| Service / Operator | Endpoint Host(s) | Purpose | Typical Hosting Jurisdiction | Transfer Safeguard |
|---|---|---|---|---|
| NCBI / NIH (PubMed, GEO, ClinVar, PubChem) | `eutils.ncbi.nlm.nih.gov`, `pubchem.ncbi.nlm.nih.gov` | Literature, expression, variant, and compound lookup | United States | `[SCC_OR_DPF_OR_PUBLIC_API_BASIS]` |
| EMBL-EBI (ChEMBL, AlphaFold DB, UniProt, GWAS Catalog, Europe PMC, QuickGO) | `www.ebi.ac.uk`, `alphafold.ebi.ac.uk`, `rest.uniprot.org` | Bioactivity, structure, protein, and literature lookup | United Kingdom / EEA | `[ADEQUACY_OR_SCC_REFERENCE]` |
| Broad Institute (gnomAD, GTEx, Single Cell Portal) | `gnomad.broadinstitute.org`, `gtexportal.org`, `singlecell.broadinstitute.org` | Genetic constraint, tissue expression, single-cell discovery | United States | `[SCC_OR_PUBLIC_API_BASIS]` |
| Open Targets, RCSB PDB, Reactome, STRING, ClinicalTrials.gov, openFDA, EPO, Allen Institute, CZI CELLxGENE, JAX (MGI/HPO), Alliance of Genome Resources, HPA, MIT ASKCOS, arXiv, bioRxiv | Respective public REST/GraphQL endpoints listed in `docs/operating-environment.md` | Public biomedical database retrieval and retrosynthesis lookup | United States / EU / Global | `[APPLICABLE_TRANSFER_MECHANISM]` |
| Optional User-Configured Cloud Prediction Endpoints (`PKDE_AF3_PROJECT`, `PKDE_AG_PROJECT`, `PKDE_PUBMED_BQ_DATASET`) | User-configured endpoint DNS (`PKDE_AG_ENDPOINT_DNS`) / region (`PKDE_AF3_REGION`, `PKDE_AG_REGION`) | Dedicated AlphaFold 3, AlphaGenome, or SQL Warehouse queries | User-selected (`[PIN_EEA_REGION_IF_REQUIRED]`) | `[CUSTOMER_CLOUD_DPA_REFERENCE]` |

## 4. Data Subject Rights (Access, Portability, Erasure)

Because all program workspaces reside on the user's local machine or organization-managed filesystem:
- **Access & Portability:** Workspace artifacts are stored in standard machine-readable formats (JSON, YAML, Markdown, CSV) under `.pkde-workspace/` or `--project <dir>`.
- **Erasure:** Deleting the workspace directory permanently removes all local artifacts, events, and logs. For organizational deployments integrating shared storage or cloud endpoints, submit erasure or portability requests to `[PRIVACY_CONTACT_EMAIL]` (target SLA: `[SLA_DAYS, e.g., 30 days]`).

## 5. Security Measures

- Local dashboard server binds to loopback (`127.0.0.1`) by default with strict Content-Security-Policy, same-origin API checks, and zero third-party script/font requests.
- Private compound datasets and proprietary algorithms executed via `pkde custom` remain strictly local (`Phase 2` runs with network sockets latched offline).
- Credentials (`NCBI_API_KEY`, `ALPHAGENOME_API_KEY`, cloud credentials) are supplied via environment variables and redacted from HTTP error logs.
