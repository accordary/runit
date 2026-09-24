# Embedded AI Diagnostics

A small local edge model that classifies runit service failures from supervision
signals and log text. It runs entirely on the device: no cloud API, no network
socket, no outbound request at any point in load or inference.

License: this component is part of runit and is covered by `COPYING.md` in the
repository root; the bundled model artefact carries the same notice inline.

## Components

| Path | Purpose |
| --- | --- |
| `scripts/edge_diag/model.json` | Bundled model artefact (~1 KiB linear-logistic weights) |
| `scripts/edge_diag/edge_model.py` | Serial loader and scorer |
| `scripts/edge_diag/diagnose.py` | Feature extraction and interpretable diagnosis |
| `scripts/edge_diag/cli.py` | Command line entry point |
| `tests/edge_diag/test_edge_diag.py` | Unit tests |

## Loading sequence

Loading is serial by construction: one module-level lock admits one loader at a
time, and the stages run in fixed order. Each stage is recorded on the loaded
model as `load_stages`, so a partial load names the stage that stopped it.

1. `locate` — resolve the artefact path (default: alongside the module).
2. `stat` — size and permission check; reject empty or oversized (> 1 MiB) files.
3. `read` — one sequential UTF-8 read into memory.
4. `parse` — JSON decode.
5. `validate` — required keys present; every class has a bias and a weight
   vector whose length matches the feature list.
6. `ready` — publish the immutable model and cache it for the process.

Failure at any stage raises `ModelLoadError` carrying `.stage` and `.detail`.
The model is loaded once per process and reused; concurrent callers queue and
receive the same object rather than loading in parallel.

## Resource requirements

| Resource | Requirement |
| --- | --- |
| Disk | ~1 KiB model artefact; ~24 KiB total source |
| Memory | < 1 MiB resident for model plus scorer; loader caps artefact reads at 1 MiB |
| CPU | Pure integer/float arithmetic, 7 features x 5 classes per inference; no BLAS, no GPU |
| Runtime | Python 3.6+ standard library only; no third-party packages |
| Network | None. The component never opens a socket |

## Diagnostics produced

Classes: `healthy`, `respawn_loop`, `dependency_stall`, `permission_fault`,
`disk_pressure`.

Every diagnosis is interpretable and returns:

- `label` and `confidence`, plus the full probability distribution;
- `features` — the extracted feature vector by name;
- `contributions` — per-feature weight x value, sorted by magnitude, so the
  reason for the label is readable directly;
- `evidence` — the actual log lines (up to five per category) that triggered
  each signal;
- `remedy` — the operator action implied by the label;
- `model_version` and `load_stages` for provenance.

## Usage

    # from the repository root
    tail -n 200 /var/log/svc/current | \
      python3 -m scripts.edge_diag.cli --exit-code 1 --restarts 12 --uptime 2

    python3 -m scripts.edge_diag.cli --log /var/log/svc/current --json

Exit status is 0 when the verdict is `healthy`, 1 otherwise, and 2 when the
model artefact cannot be loaded.

## Tests

    cd /path/to/runit && python3 -m unittest discover -s tests/edge_diag -v
