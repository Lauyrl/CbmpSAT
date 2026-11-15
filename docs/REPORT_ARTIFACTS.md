# Report artifact and source map

This file inventories the assets displayed by report/report.tex. It distinguishes (a) values embedded in the manuscript and sourced from historical phase archives, (b) curated image files under report/figures/, and (c) fresh outputs under results/.

## 1. Quantitative tables embedded in the manuscript

The following tables are written directly in LaTeX; they are not loaded from results/tables/ at compile time.

| Report label | Manuscript content | Historical source artifact | Current-snapshot status |
|---|---|---|---|
| tab:table_solvers_small | SAT solver comparison, four small instances | docs/phaseC/table_solvers_small.csv | Historical; current snapshot does not contain the small solver group. |
| tab:table_solvers_medium | SAT solver comparison, medium instances | docs/phaseC/table_solvers_medium.csv | Historical; current snapshot has 20 medium solver records, but does not reproduce this archived table. |
| tab:table_methods | SAT / CP-SAT / CPLEX MIP comparison | docs/phaseC/table_methods.csv | Historical seven-instance table; current exact-solver batch covers four small datasets. |
| tab:table_methods_large | SAT / CP-SAT large-instance comparison | docs/phaseC/table_methods_large.csv | Historical; not regenerated from current snapshot. |
| tab:table_per_dataset | SAT per-dataset summary | docs/phaseC/table_per_dataset.csv | Historical 16-instance table; not regenerated from current snapshot. |
| Ablation small table | Five-variant small-graph ablation | docs/phaseD/table_ablation_small.csv | Historical; current snapshot has no ablation-small group. |
| Ablation medium table | 662_bus_n60 ablation | docs/phaseD/table_ablation_medium.csv | Historical; current snapshot has no ablation-medium group. |
| Ablation family table | Randomized-label paired comparisons | docs/phaseD/table_ablation_family.csv | Historical; current snapshot has no ablation-family group. |
| Phase decomposition table | Previous/last iteration timing | docs/phaseD/table_ablation_phases.csv | Historical; current snapshot has no phase-decomposition group. |

The files under results/tables/ (for example table_methods.csv, table_solvers.csv, and table_ablation.csv) are generated from the current raw snapshot by analysis/make_tables.py. They have different coverage and aggregation and must not be substituted for report tables solely because their names are similar.

## 2. Figure files referenced by the report

All paths below are relative to the report/ directory.

| Report figure | File | Provenance interpretation |
|---|---|---|
| fig:cactus_solvers | figures/cactus_solvers_small.png, figures/cactus_solvers_medium.png | Curated report assets; historical Phase C comparison, not established as regenerated from current raw snapshot. |
| fig:cnsplots_encoding_comparison | figures/cnsplots_encoding_comparison.png | Optional and currently absent; guarded by IfFileExists, so the manuscript omits it. |
| Ablation cactus / family figures | figures/cactus_ablation_medium.png, figures/boxplot_ablation_family.png | Curated historical Phase D assets, not established as regenerated from current raw snapshot. |
| Other report figures | figures/ablation_iterations_and_unsat_medium.png, figures/ablation_iterations_and_unsat_small.png, figures/ablation_median_time_medium.png, figures/ablation_median_time_small.png, figures/cactus_ablation_small.png, figures/cactus_methods.png, figures/scatter_sb_vs_nosb_small.png | Tracked report assets; retain as report archive. Their exact raw-run provenance is not established by file presence alone. |

The report figure assets are not automatically synchronized with results/figures/. A PNG in report/figures/ must not be described as generated from the current snapshot unless its input hash, generation command, source commit, environment, and timestamp are recorded.

## 3. Current output namespace

| Path | Meaning | Used directly by report? |
|---|---|---|
| results/runs.jsonl | Current tracked raw exploratory records | No; used as input to analysis scripts. |
| results/env.json | Environment/source metadata for current snapshot | No; cited descriptively in manuscript/data availability. |
| results/tables/ | Tables generated from current raw records | No; not imported by the LaTeX manuscript. |
| results/figures/ | Figures generated from current raw records | No; report uses curated files in report/figures/. |
| docs/phaseC/, docs/phaseD/ | Historical tables supporting manuscript values | Yes, as documented evidence sources for embedded values. |

## 4. Updating a report artifact safely

1. Select one raw JSONL archive and verify its source commit, cleanliness, configuration, dataset identity, and solver statuses.
2. Generate the table/figure into a staging directory; do not overwrite historical phase artifacts.
3. Compare every displayed value and sample count against the generated artifact.
4. Copy the accepted asset into the report only after validation.
5. Update this map with the new raw input, output path, generation command, source commit, environment, timestamp, and any exclusions.
6. Update manuscript wording so that the stated sample size, dataset coverage, timeout semantics, and provenance match the new artifact.

## 5. Known limitation

The repository currently tracks historical report tables and curated figures alongside a newer but exploratory raw snapshot. This map makes the distinction explicit; it does not claim that the historical figures have complete raw-run provenance or that the current snapshot reproduces the historical manuscript results. A clean benchmark rerun and report regeneration remain user-executed experimental work.