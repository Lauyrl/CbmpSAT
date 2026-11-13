# Integration Analysis: CBMP into Lauyrl/CbmpSAT

## 1. Repository Architecture Analysis
The current repository (`datnk0116/CBMP`) is an evolved version of the original `Lauyrl/CbmpSAT` structure. The target repository is a simpler, foundational version, while this one has significant additions in testing, reporting, and comprehensive experimental infrastructure.

## 2. Component Mapping

| Component | Target Repository | Current CBMP | Action |
|---|---|---|---|
| Core Encodings | `alo_amo_eo_encodings.py`, `sat_encodings.py` | Same | Reuse (verify parity) |
| Problem Logic | `cbmp.py`, `bmp.py` | Same | Adapt to maintain consistency |
| Execution Logic | `run_experiments.py` | `experiments/run_experiments.py` | Replace/Merge (ours is more robust) |
| Tests | Minimal/None | `tests/` directory (very comprehensive) | Integrate tests |
| Reporting | Minimal | `analysis/`, `report/`, `reports/` | Integrate as optional reporting tools |
| Baselines | None | `baselines/` | Integrate as optional solvers |

## 3. Merge Strategy
- **Core modules**: Keep the refined implementations in `cbmp.py`, `sat_encodings.py`.
- **Infrastructure**: The experiment runner `experiments/run_experiments.py` is significantly more capable than the target's version. We should propose replacing the target's runner.
- **Cleanup**: Remove temporary artifacts (`.DS_Store`, `__pycache__`, legacy files).
- **Git**: Ensure no AI-related files (`CLAUDE.md`, etc.) are tracked.
- **Documentation**: Add `docs/INTEGRATION_WITH_CBMPSAT.md` explaining the merge plan.

## 4. Compatibility status (checked against `target/main`)

| Target file | Status |
|---|---|
| `bmp.py` | Identical to ours (moved from `legacy/` back to root) — merges as a no-op. |
| `alo_amo_eo_encodings.py` | Superset: all target functions (`exactly_one_product`, `exactly_one_commander`, `at_most_one_commander_*`) kept with same signatures. |
| `sat_encodings.py` | Superset: `cyclic_edge` / `break_reflection_symmetry` kept as aliases of the order-encoding versions (identical clauses). `injectivity_surjectivity_X` 4th arg renamed `eo_encoding` → `eo_strategy` (positional calls still work). |
| `cbmp.py` | `solve(...)` positional order changed (`sb_rotation, sb_reflection` replace `use_symmetry_break`); keyword `use_symmetry_break=` still accepted. |
| `main.py` | **Breaking**: `main(dataset, sb_rotation, sb_reflection, use_heuristic_initial_ub, timeout, ...)` returns a stats dict, not `(ub, solve_time)`. |
| `run_experiments.py` | Replaced by a root shim forwarding to `experiments/run_experiments.py`. Take ours when resolving the add/add conflict; the target version is incompatible with the new `main()`. |
| `datasets/*.mtx` | Target datasets are a subset of ours. |
| `results/experiment_results.csv` | Target-only; keep as historical evidence. |

New, non-overlapping: `baselines/`, `experiments/`, `tests/`, `analysis/`, `scripts/`, `docs/`, `reports/`, `graph_utils.py`, `pytest.ini`.
