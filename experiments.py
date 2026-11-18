"""Schedule CBMP experiments and export checkpointed result records."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cbmp import DATASETS, SatConfig, load_instance, solve_timed
from helper.helper import (canonical, completed_keys, display_name, export_csv,
                           read_lower_bounds, write_record)
from helper.plots import plot_ablation, plot_encoding, plot_incumbents, plot_methods
from solvers import cp_sat, cplex_cp, cplex_mip, gurobi

EXEMPLARS = ("dwt_234", "impcol_d", "bcsstk06", "494_bus", "662_bus", "can_715")
LARGE = ("494_bus", "662_bus", "can_715")
EXTERNAL_SOLVERS = {
    "CP-SAT": cp_sat.solve,
    "CPLEX CP": cplex_cp.solve,
    "CPLEX MIP": cplex_mip.solve,
    "Gurobi": gurobi.solve,
}


def record_base(group: str, instance, method: str, result: dict,
                lower_bounds: dict[str, int], **settings) -> dict:
    lb = lower_bounds.get(canonical(instance.name))
    ub = result.get("best_ub")
    return {
        "group": group,
        "instance": instance.name,
        "method": method,
        "n": instance.n,
        "edges": len(instance.edges),
        "known_lb": lb,
        "gap": None if ub is None or lb is None else ub - lb,
        **settings,
        **result,
    }


def sat_config(config: dict) -> SatConfig:
    level = config.get("level", "strong")
    symmetry = "reflection"
    heuristic = True
    if level == "weak":
        symmetry, heuristic = "none", False
    elif level == "medium":
        symmetry, heuristic = "rotation", False
    elif level == "no_rotation":
        symmetry = "none"
    elif level == "no_reflection":
        symmetry = "rotation"
    elif level == "no_heuristic":
        heuristic = False

    return SatConfig(
        distance=config.get("distance", "order"),
        exactly_one=config.get("exactly_one", "product"),
        symmetry=symmetry,
        heuristic=heuristic,
    )


def group_jobs(group: str):
    if group == "methods":
        return [(method, {}) for method in ("SAT", *EXTERNAL_SOLVERS)]
    if group == "encodings":
        return [(distance, {"distance": distance, "exactly_one": eo})
                for distance, eo in (("direct", "product"), ("order", "product"), ("order", "pairwise"))]
    if group == "ub-time":
        return [("SAT", {"distance": "order", "exactly_one": "product"})]
    return [(level, {"level": level}) for level in
            ("weak", "medium", "strong", "no_rotation", "no_reflection", "no_heuristic")]


def run_group(group: str, datasets: list[str], timeout: int, output: Path, force: bool):
    directory = output / group
    directory.mkdir(parents=True, exist_ok=True)
    records_path = directory / "records.jsonl"
    done = set() if force else completed_keys(records_path)
    lower_bounds = read_lower_bounds(DATASETS / "lb.csv")

    for name in datasets:
        instance = load_instance(name)
        for method, config in group_jobs(group):
            key = json.dumps([name, method, config], sort_keys=True)
            if key in done:
                continue

            if method == "SAT" or group != "methods":
                result = solve_timed(instance, sat_config(config), timeout).as_dict()
            else:
                result = EXTERNAL_SOLVERS[method](instance, timeout)

            record = record_base(group, instance, method, result, lower_bounds,
                                 timeout_seconds=timeout, **config)
            record["key"] = key
            write_record(records_path, record)

    rows = export_csv(records_path, directory / "results.csv")
    if group == "methods":
        plot_methods(rows, directory)
    elif group == "encodings":
        plot_encoding(rows, directory)
    elif group == "ub-time":
        plot_incumbents(rows, directory)
    elif group == "ablation":
        plot_ablation(rows, directory)
    return rows


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("group", choices=("methods", "encodings", "ub-time", "ablation", "all"))
    parser.add_argument("--timeout", type=int, default=1200, help="per-setting wall-clock limit in seconds")
    parser.add_argument("--output", type=Path, default=Path("results"))
    parser.add_argument("--datasets", nargs="*", help="override the group's default instances")
    parser.add_argument("--force", action="store_true", help="rerun completed settings")
    return parser.parse_args()


def main():
    args = parse_args()
    groups = ("methods", "encodings", "ub-time", "ablation") if args.group == "all" else (args.group,)
    for group in groups:
        defaults = (tuple(display_name(path.stem) for path in DATASETS.glob("*.mtx")) if group == "methods"
                    else LARGE if group == "ub-time" else EXEMPLARS)
        run_group(group, args.datasets or list(defaults), args.timeout, args.output, args.force)


if __name__ == "__main__":
    main()
