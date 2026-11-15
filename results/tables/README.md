# Current result tables

Generated from the latest tracked raw input, `results/runs.jsonl`.

- Raw input blob SHA: `2450b988cabcf57fff98af6580a128ea99c849a9`
- Raw records: **44**
- Status counts: OPTIMAL=24, TIMEOUT=12, UNAVAILABLE=4, SIZE_LIMIT=3, FEASIBLE=1
- Group memberships: `exact_solvers` 24, `solvers_medium` 20, `encodings` 4. These memberships overlap; do not sum them to infer unique records.
- Datasets with records: 14_bus, 30_bus, 494_bus_n40, 494_bus_n60, 494_bus_n80, 662_bus_n40, 662_bus_n60, 662_bus_n80.

## Tables

- `table_encoding_comparison.csv`: per-dataset Order and Pairwise results. Uses SAT records from both `encodings` and `exact_solvers`.
- `table_encoding_comparison_pairs.csv`: matched configuration/repetition summary. Each current dataset has one paired run; this is a paired single-run comparison, not repeated-trial statistics.
- `table_exact_solvers.csv`: 24 exact-solver rows. Preserves OPTIMAL, FEASIBLE, SIZE_LIMIT, and UNAVAILABLE distinctly.
- `table_solvers_medium.csv`: 20 medium SAT solver rows. Includes both solver `solve_time_s` and process `wall_time_s`.

For TIMEOUT rows, an incumbent UB is not a proof of optimality; process wall time is the elapsed runtime. Do not compare solver `solve_time` to timeout wall time as if they measure the same thing.

Regenerate all four tables with:

```bash
python analysis/make_tables.py results/runs.jsonl --output-dir results/tables
```

Review the generated outputs before committing. The raw JSONL is the source; CSV files are derived artifacts.
