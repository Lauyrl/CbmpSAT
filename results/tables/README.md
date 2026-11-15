# Current result tables

Generated from the latest tracked raw input, `results/runs.jsonl`.

- Raw input blob SHA: `2450b988cabcf57fff98af6580a128ea99c849a9`
- Raw records: **44**
- Status counts: OPTIMAL=24, TIMEOUT=12, UNAVAILABLE=4, SIZE_LIMIT=3, FEASIBLE=1
- Group memberships: `exact_solvers` 24, `solvers_medium` 20, `encodings` 4. These memberships overlap; do not sum them to infer unique records.
- Datasets with records: 14_bus, 30_bus, 494_bus_n40, 494_bus_n60, 494_bus_n80, 662_bus_n40, 662_bus_n60, 662_bus_n80.
- Encoding comparisons use SAT records from both `encodings` and `exact_solvers`. Each dataset has one run per encoding; the pairs are controlled by dataset, solver, and SAT configuration, but are not repeated runs.
- The medium-solver table includes both `solve_time_s` and `wall_time_s`. For TIMEOUT records, an incumbent UB is not a proof of optimality; wall time is the elapsed process time.
- The exact-solver table preserves `SIZE_LIMIT`, `UNAVAILABLE`, and `FEASIBLE` as distinct statuses.

Only the current snapshot is represented. Regenerate these outputs with `python analysis/make_tables.py results/runs.jsonl --output-dir results/tables` after adding new records and review the outputs before committing.
