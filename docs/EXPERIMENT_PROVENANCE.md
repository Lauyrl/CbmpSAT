# Experiment and report provenance

This document defines which tracked data is current, which data is historical, and which archived phase tables support the quantitative tables in `report/report.tex`.

## 1. Data tiers (do not merge)

| Location | Records / contents | Role | Reproducibility interpretation |
|---|---:|---|---|
| `results/runs.jsonl` + `results/env.json` | 44 records | Current tracked exploratory snapshot | All records carry `git_dirty=true`; source tree cannot be reconstructed from the commit hash alone. Do not label as a clean reproducible benchmark. |
| `docs/data/runs.jsonl` + `docs/data/env.json` | 207 records | Historical experiment archive | Records identify multiple clean source commits. Preserve as a distinct archive. |
| `docs/data/runs_ablation.jsonl` | 255 records | Historical ablation archive | Separate archive; records identify commit `89603149159ef65b2b6a5220ad59a80d80a0d09c`. Do not append to `runs.jsonl`. |

### Current snapshot composition

The 44 records in `results/runs.jsonl` are distributed as follows:

| Group | Records | Status composition | Dataset coverage |
|---|---:|---|---|
| `encodings` | 4 | 4 OPTIMAL | 14_bus, 30_bus, 494_bus_n40, 662_bus_n40 |
| `exact_solvers` | 24 | 16 OPTIMAL, 4 UNAVAILABLE, 3 SIZE_LIMIT, 1 FEASIBLE | 14_bus, 30_bus, 494_bus_n40, 662_bus_n40 |
| `solvers_medium` | 20 | 8 OPTIMAL, 12 TIMEOUT | 494_bus_n60, 494_bus_n80, 662_bus_n60, 662_bus_n80 |

These group counts sum to 48 because a record may belong to more than one group. The JSONL contains 44 unique records; do not sum group totals to infer record count. Within the four encoding records, three use Order Encoding and one uses Pairwise Encoding. A single Pairwise observation is not sufficient for a robust paired performance conclusion.

## 2. Configured experiment-group coverage

The experiment configuration defines 14 groups. In the current 44-record snapshot, only three group labels occur; the other 11 are configured but have no records in this snapshot. Configuration presence is not evidence of execution.

| Group | Present in current snapshot | Interpretation |
|---|---|---|
| `encodings` | Yes (4 records) | Partial encoding comparison; one Pairwise record is insufficient for robust paired claims. |
| `exact_solvers` | Yes (24 records) | Partial batch on four small instances. |
| `solvers_medium` | Yes (20 records) | Partial medium solver batch on four configured instances. |
| `per_dataset` | No | Configured; no current records. |
| `solvers_small` | No | Configured; no current records. |
| `methods` | No | Configured; no current records. |
| `ablation_small` | No | Configured; no current records. |
| `ablation_medium` | No | Configured; no current records. |
| `ablation_family` | No | Configured; no current records. |
| `methods_family` | No | Configured; no current records. |
| `cpsat_large` | No | Configured; no current records. |
| `methods_large_seeds` | No | Configured; no current records. |
| `cplex_cp` | No | Configured; no current records. |
| `gurobi` | No | Configured; no current records. |

This coverage statement is tied to the 44-record snapshot and must be refreshed whenever `results/runs.jsonl` changes.

## 3. Retained phase archives

Only `docs/phaseC/` and `docs/phaseD/` remain in this branch. They are separate historical research snapshots, not sequential database migrations:

- `docs/phaseC/`: method, per-dataset, solver, large-instance and cross-validation outputs. Its cross-validation file records optimum-agreement checks for that archived phase.
- `docs/phaseD/`: ablation-family, small/medium ablation and phase-decomposition outputs.

Earlier Phase A/A2/B, pilot and calibration artifacts were removed from this branch. They must not be referenced as available files or treated as current evidence. The retained C/D tables are historical snapshots; their presence does not prove that all underlying raw runs are retained or that the current snapshot reproduces them.

## 4. Report table source mapping

The quantitative tables in the current LaTeX report are historical, manually retained summaries. Their corresponding archived phase artifacts are:

| Report table / content | Archived source artifact | Important qualification |
|---|---|---|
| SAT solver small comparison | `docs/phaseC/table_solvers_small.csv` | Historical solver comparison; not the current 44-record batch. |
| SAT solver medium comparison | `docs/phaseC/table_solvers_medium.csv` | Historical table coverage differs from the current snapshot, which has 20 medium-solver records. |
| Methods comparison (SAT / CP-SAT / CPLEX MIP) | `docs/phaseC/table_methods.csv` | Seven-instance historical comparison; current exact-solver batch covers four small datasets only. |
| Large methods comparison | `docs/phaseC/table_methods_large.csv` | Historical SAT/CP-SAT large-instance comparison. |
| Per-dataset SAT summary | `docs/phaseC/table_per_dataset.csv` | Historical 16-instance table; not generated from current snapshot. |
| Ablation small | `docs/phaseD/table_ablation_small.csv` | Historical five-variant ablation summary. |
| Ablation medium | `docs/phaseD/table_ablation_medium.csv` | Historical 662_bus_n60 summary. |
| Ablation family | `docs/phaseD/table_ablation_family.csv` | Historical 30-pair randomized-label comparison. |
| Phase decomposition | `docs/phaseD/table_ablation_phases.csv` | Historical median previous/last iteration timing summary. |

The corresponding `cross_validation.csv` files in Phase C and Phase D provide supporting optimum-consistency checks for those phase archives. A `verified` value in a phase cross-validation file is evidence for that archived validation operation; it is not proof that the current snapshot reproduces the phase's runtime measurements.

## 5. Figures and output directories

- `analysis/figures/`: analysis figures retained in the source tree.
- `results/figures/`: generated outputs associated with the current `results/` input.
- `report/figures/`: curated figure assets used by the LaTeX report.

The report currently includes solver cactus plots, a medium ablation cactus plot and an ablation-family boxplot from `report/figures/`. The optional `figures/cnsplots_encoding_comparison.png` is not present; the report guards it with `\\IfFileExists`. Do not imply that this optional image was generated from the four current encoding records unless a generated artifact and its input provenance are archived.

A figure copied into `report/figures/` is not automatically reproducible from the current snapshot. To establish that, retain the input JSONL hash, source commit, command line, package environment and generation timestamp alongside the figure.

## 6. Rules for future experiments and report updates

1. Commit the exact source tree before running a benchmark. Record a clean commit and `git_dirty=false`.
2. Store the raw JSONL and its environment metadata together in `results/`; do not merge runs from different source commits or incompatible configurations.
3. Use `docs/data/`, `docs/phaseC/` and `docs/phaseD/` as immutable historical evidence. Do not append new runs to these archives.
4. Regenerate tables and plots from a single explicitly identified raw input. Record the input file hash, command, source commit and environment.
5. Update the mapping in this file whenever a report table or figure is replaced.
6. Treat `UNAVAILABLE`, `SIZE_LIMIT`, `LICENSE_ERROR`, `TIMEOUT` and `FEASIBLE` as distinct solver outcomes. Never infer a timeout or runtime for a solver without a corresponding record.
7. Do not call the current 44-record snapshot a final/reproducible benchmark until it is replaced by or supplemented with a clean, fully documented run.

## 7. Distinguish report assets from current generated outputs

The LaTeX report does not automatically include files from `results/tables/` or `results/figures/`. Its numerical tables are embedded directly in `report/report.tex`, and its included image assets are under `report/figures/`. The files with generic names under `results/tables/` are separate outputs generated from the current `results/runs.jsonl`; matching names such as `table_methods` do not mean they are the report's source. See `docs/REPORT_ARTIFACTS.md` for the explicit table-label and figure-file mapping.

Never describe a current generated table as the source of a historical report table unless the report is deliberately updated from that exact file and the raw input, generation command, source commit, and environment are recorded.

## 8. Snapshot identity at the time this document was written

- Current raw input: `results/runs.jsonl`
- Environment metadata: `results/env.json`
- Recorded source: `41271c4119a306ace4b42e734093ea773ab30bc2-dirty`
- Recorded environment timestamp: `2026-11-15T08:40:57Z`
- Unique raw records: 44

These values describe the committed snapshot at this revision. If `results/` is updated, refresh this section and the current snapshot composition table from the new raw files.
