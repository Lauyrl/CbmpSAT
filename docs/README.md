# Documentation and experiment archive

This directory preserves historical experiment artifacts. It is deliberately separate from the active pipeline.

## Active versus archived data

- **Active snapshot:** `results/runs.jsonl` and its paired `results/env.json`.
- **Derived active outputs:** `results/tables/` and `results/figures/`, generated from that snapshot.
- **Historical archive:** everything under this `docs/` directory. These files are not the default input to `experiments/run_experiments.py`, `analysis/make_tables.py`, or `analysis/make_plots.py`.

Do not concatenate historical JSONL files with `results/runs.jsonl` unless a deliberate data-integration study has first checked schema compatibility, run identity, source commit, configuration, dataset version, and duplicate/conflicting records.

## Archive inventory

| Path | Contents | Intended interpretation |
|---|---|---|
| `docs/data/env.json` | Environment metadata associated with the historical raw runs | Provenance metadata for that historical collection |
| `docs/data/runs.jsonl` | Historical experiment records (207 records in the audited snapshot) | Raw historical runs; not the current snapshot |
| `docs/data/runs_ablation.jsonl` | Historical ablation records (255 records in the audited snapshot) | Raw historical ablation runs; not the current snapshot |
| `docs/phaseC/` | Cross-validation, lower-bound check, methods and solver tables (CSV/TeX) | Expanded historical analysis outputs |
| `docs/phaseD/` | Cross-validation and ablation-family/medium/phase tables (CSV/TeX) | Later historical ablation outputs |

The directory names establish organization, not a complete reproducibility guarantee. Do not infer that one phase supersedes another, or that two similarly named tables are directly comparable, without examining their raw inputs and configuration.

## Provenance requirements for future archive additions

For every new phase/archive, include a short README or metadata file recording:

1. purpose and research question;
2. exact raw input file(s) and dataset manifest/version;
3. configuration and command line;
4. source Git commit and whether the working tree was clean;
5. solver/library versions, timeout and hardware where available;
6. generation date and script used;
7. known limitations and whether the table is reproduced from raw records.

Keep archived artifacts immutable. If a correction is needed, add a clearly versioned corrected artifact and explain the relationship; do not silently replace historical evidence.

## Figure locations

- `analysis/figures/`: analysis-side figures retained in the source tree; generated output should normally go to `results/figures/`.
- `results/figures/`: generated figures corresponding to the active `results/runs.jsonl` snapshot.
- `report/figures/`: selected, report-ready figures referenced by the LaTeX manuscript. These are presentation assets and may originate from historical analysis; do not assume they match the active snapshot unless regenerated and checked.

## Removed archival material

The `phaseA`, `phaseA2`, `phaseB`, pilot, and tracked calibration artifacts were deliberately removed from this branch. They are not part of the active experiment pipeline and must not be cited as files available here. Historical conclusions that depended on those artifacts no longer have their supporting files in this branch. The retained Phase C/Phase D report tables remain historical snapshots; see `EXPERIMENT_PROVENANCE.md` and `REPORT_ARTIFACTS.md` for their limitations.
