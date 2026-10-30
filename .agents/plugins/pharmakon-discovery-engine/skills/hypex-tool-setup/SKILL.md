---
name: hypex-tool-setup
description: "Activate and verify the PkDE-provisioned Hypex tools before running a hypothesis-exploration workflow."
---

# Hypex Tool Setup in PkDE

The PkDE bootstrapper provisions `hypex`, `elo`, and `prox` from the source
vendored in `applications/PkDE/tools/vendor/hypex`. Literature access is part
of the `pkde` CLI; there is no separate `lit` executable in PkDE.

## Activate

Source the generated environment file, not the venv activation script:

```bash
source "${PKDE_ROOT:-.}/bin/env.sh"
```

This activates the PkDE venv, adds `tools/bin` to `PATH`, sets
`PKDE_TOOLS_HOME`, and selects the provisioned environment stamp.

## Verify

```bash
pkde doctor --json
hypex --help
elo --help
prox --help
```

`pkde doctor` must report `binary hypex`, `binary elo`, `binary prox`, and
`hypothesis strategy: hypex` as `ok`. A missing or non-runnable command is a
capability failure. Report it to the supervisor; do not build tools ad hoc in
a worker container or install packages into the shared venv.

## Tool Inventory

| Tool | Provisioning | Purpose |
|---|---|---|
| `pkde` | PkDE Python package | Literature, citations, Hypex ingest/analyze, and PkDE artifacts |
| `hypex` | Vendored Go source | Hypothesis datastore lifecycle and schema validation |
| `elo` | Vendored Go source | Tournament pairings, ratings, and standings |
| `prox` | Vendored Python source | Similarity, clustering, and near-duplicate detection |

The bootstrapper is the only owner of provisioning. Repair a missing tool by
re-running `applications/PkDE/tools/install.sh`; `--binaries-only` is suitable
when the full Python environment, including prox dependencies, already exists.
