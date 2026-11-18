"""Reproducible CBMP experiments for the bundled Harwell--Boeing instances."""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from pysat.solvers import Cadical195
from scipy.io import mmread
from scipy.sparse.csgraph import reverse_cuthill_mckee

from alo_amo_eo_encodings import exactly_one as encode_exactly_one
from helper.helper import (canonical, completed_keys, display_name, export_csv, find_instance_path,
                           read_lower_bounds, write_record)
from helper.plots import plot_ablation, plot_encoding, plot_incumbents, plot_methods
from sat_encodings import (biconditional_X_and_G, break_reflection_symmetry,
                           break_reflection_symmetry_direct, break_rotation_symmetry, cyclic_edge,
                           direct_cyclic_edge, direct_edge_clause_count, injectivity_surjectivity_X,
                           lower_upper_bound_G, monotonic_G)
from solvers import cp_sat, cplex_cp, cplex_mip, gurobi

DATASETS = Path(__file__).with_name("datasets")
EXEMPLARS = ("dwt_234", "impcol_d", "bcsstk06", "494_bus", "662_bus", "can_715")
LARGE = ("494_bus", "662_bus", "can_715")
MAX_DIRECT_CLAUSES = 25_000_000
EXTERNAL_SOLVERS = {
    "CP-SAT": cp_sat.solve,
    "CPLEX CP": cplex_cp.solve,
    "CPLEX MIP": cplex_mip.solve,
    "Gurobi": gurobi.solve,
}


@dataclass
class Instance:
    name: str
    n: int
    edges: list[tuple[int, int]]
    graph: object


def load_instance(name: str) -> Instance:
    graph = mmread(find_instance_path(DATASETS, name)).tocsr()
    rows, cols = graph.nonzero()
    edges = [(int(u), int(v)) for u, v in zip(rows, cols) if u < v]
    return Instance(name, graph.shape[0], edges, graph)


def cyclic_bandwidth(n: int, edges: Iterable[tuple[int, int]], assignment) -> int:
    return max(min(abs(assignment[u] - assignment[v]), n - abs(assignment[u] - assignment[v])) for u, v in edges)


def heuristic_upper_bound(instance: Instance) -> int:
    permutation = reverse_cuthill_mckee(instance.graph, symmetric_mode=False)
    assignment = np.empty(instance.n, dtype=int)
    assignment[permutation] = np.arange(instance.n)
    return int(cyclic_bandwidth(instance.n, instance.edges, assignment))


# SAT construction and execution stay here because they are CBMP-specific.
def make_sat_formula(instance: Instance, distance: str, eo_encoding: str, symmetry: str):
    n = instance.n
    X = [[1 + vertex * n + label for label in range(n)] for vertex in range(n)]
    next_var = 1 + n * n
    clauses: list[list[int]] = []

    if distance == "direct":
        for vertex in range(n):
            encoded, next_var = encode_exactly_one(X[vertex], next_var, eo_encoding)
            clauses.extend(encoded)
        for label in range(n):
            encoded, next_var = encode_exactly_one([X[vertex][label] for vertex in range(n)], next_var, eo_encoding)
            clauses.extend(encoded)
        G = None
    elif distance == "order":
        g_start = next_var
        G = [[g_start + vertex * (n + 1) + label for label in range(n + 1)] for vertex in range(n)]
        next_var = g_start + n * (n + 1)
        assignment, next_var = injectivity_surjectivity_X(n, X, next_var, eo_encoding)
        clauses.extend(assignment)
        clauses.extend(monotonic_G(n, G))
        clauses.extend(lower_upper_bound_G(n, G))
        clauses.extend(biconditional_X_and_G(n, X, G))
    else:
        raise ValueError(f"unknown distance encoding: {distance}")

    if symmetry in {"rotation", "reflection"}:
        clauses.extend(break_rotation_symmetry(X, 0))
    if symmetry == "reflection":
        clauses.extend(break_reflection_symmetry_direct(n, X) if distance == "direct"
                       else break_reflection_symmetry(n, X, G))

    def add_edge_constraints(solver, upper_bound: int) -> int:
        count = 0
        for u, v in instance.edges:
            edge_clauses = (direct_cyclic_edge(n, X, u, v, upper_bound) if distance == "direct"
                            else cyclic_edge(n, X, G, u, v, upper_bound))
            solver.append_formula(edge_clauses)
            count += len(edge_clauses)
        return count

    return clauses, next_var - 1, add_edge_constraints


def extract_assignment(model, n: int) -> list[int]:
    assignment = [0] * n
    for literal in model:
        if 0 < literal <= n * n:
            vertex, label = divmod(literal - 1, n)
            assignment[vertex] = label
    return assignment


def run_sat(instance: Instance, *, distance="order", exactly_one="product", symmetry="reflection",
            heuristic=True, checkpoint=None) -> dict:
    started = time.monotonic()
    initial_ub = heuristic_upper_bound(instance) if heuristic else instance.n // 2 + 1
    if distance == "direct":
        estimated = len(instance.edges) * direct_edge_clause_count(instance.n, initial_ub)
        if estimated > MAX_DIRECT_CLAUSES:
            return {"status": "ENCODING_FAILED", "best_ub": None, "encoding_time": 0.0,
                    "solve_time": 0.0, "variables": None, "clauses": estimated,
                    "message": f"estimated {estimated:,} direct clauses exceeds safety limit"}

    clauses, variables, add_constraints = make_sat_formula(instance, distance, exactly_one, symmetry)
    encoding_time = time.monotonic() - started
    solver = Cadical195()
    solver.append_formula(clauses)
    clause_count = len(clauses)
    initial_clause_count = None
    ub = initial_ub
    incumbents = []

    try:
        while True:
            clause_count += add_constraints(solver, ub)
            initial_clause_count = initial_clause_count or clause_count
            if not solver.solve():
                return {"status": "OPTIMAL", "best_ub": ub, "encoding_time": encoding_time,
                        "solve_time": time.monotonic() - started - encoding_time, "variables": variables,
                        "clauses": initial_clause_count, "incumbents": incumbents}

            ub = cyclic_bandwidth(instance.n, instance.edges, extract_assignment(solver.get_model(), instance.n))
            incumbents.append({"elapsed": time.monotonic() - started, "ub": ub})
            if checkpoint:
                checkpoint(ub, incumbents)
    finally:
        solver.delete()


def _sat_worker(queue, incumbent, instance, options):
    def checkpoint(upper_bound, _incumbents):
        incumbent.value = upper_bound

    try:
        queue.put(run_sat(instance, checkpoint=checkpoint, **options))
    except Exception as error:
        queue.put({"status": "ERROR", "best_ub": incumbent.value if incumbent.value >= 0 else None,
                   "encoding_time": None, "solve_time": None, "variables": None, "clauses": None,
                   "message": repr(error)})


def run_sat_timed(instance: Instance, timeout: int, **options) -> dict:
    """Run SAT in a child process because CaDiCaL cannot be interrupted safely."""
    incumbent = mp.Value("i", heuristic_upper_bound(instance) if options.get("heuristic", True) else -1)
    queue = mp.Queue()
    process = mp.Process(target=_sat_worker, args=(queue, incumbent, instance, options))
    started = time.monotonic()
    process.start()
    process.join(timeout)
    elapsed = time.monotonic() - started

    if process.is_alive():
        process.terminate()
        process.join()
        return {"status": "TIMEOUT", "best_ub": incumbent.value if incumbent.value >= 0 else None,
                "encoding_time": None, "solve_time": elapsed, "variables": None, "clauses": None,
                "incumbents": ([{"elapsed": 0.0, "ub": incumbent.value}] if incumbent.value >= 0 else [])}
    if not queue.empty():
        return queue.get()
    return {"status": "ERROR", "best_ub": None, "encoding_time": None, "solve_time": elapsed,
            "variables": None, "clauses": None, "message": f"worker exited with code {process.exitcode}"}


def record_base(group: str, instance: Instance, method: str, result: dict,
                lower_bounds: dict[str, int], **settings) -> dict:
    lb = lower_bounds.get(canonical(instance.name))
    ub = result.get("best_ub")
    return {"group": group, "instance": instance.name, "method": method, "n": instance.n,
            "edges": len(instance.edges), "known_lb": lb, "gap": None if ub is None or lb is None else ub - lb,
            **settings, **result}


def run_group(group: str, datasets: list[str], timeout: int, output: Path, force: bool):
    directory = output / group
    directory.mkdir(parents=True, exist_ok=True)
    records_path = directory / "records.jsonl"
    done = set() if force else completed_keys(records_path)
    lower_bounds = read_lower_bounds(DATASETS / "lb.csv")

    if group == "methods":
        jobs = [(method, {}) for method in ("SAT", *EXTERNAL_SOLVERS)]
    elif group == "encodings":
        jobs = [(distance, {"distance": distance, "exactly_one": eo})
                for distance, eo in (("direct", "product"), ("order", "product"), ("order", "pairwise"))]
    elif group == "ub-time":
        jobs = [("SAT", {"distance": "order", "exactly_one": "product"})]
    else:
        jobs = [(level, {"level": level}) for level in
                ("weak", "medium", "strong", "no_rotation", "no_reflection", "no_heuristic")]

    for name in datasets:
        instance = load_instance(name)
        for method, config in jobs:
            key = json.dumps([name, method, config], sort_keys=True)
            if key in done:
                continue

            if method == "SAT" or group != "methods":
                level = config.get("level", "strong")
                options = {"symmetry": "reflection", "heuristic": True}
                if level == "weak": options.update(symmetry="none", heuristic=False)
                elif level == "medium": options.update(symmetry="rotation", heuristic=False)
                elif level == "no_rotation": options.update(symmetry="none")
                elif level == "no_reflection": options.update(symmetry="rotation")
                elif level == "no_heuristic": options.update(heuristic=False)
                result = run_sat_timed(instance, timeout, distance=config.get("distance", "order"),
                                       exactly_one=config.get("exactly_one", "product"), **options)
            else:
                result = EXTERNAL_SOLVERS[method](instance, timeout)

            record = record_base(group, instance, method, result, lower_bounds, timeout_seconds=timeout, **config)
            record["key"] = key
            write_record(records_path, record)

    rows = export_csv(records_path, directory / "results.csv")
    if group == "methods": plot_methods(rows, directory)
    if group == "encodings": plot_encoding(rows, directory)
    if group == "ub-time": plot_incumbents(rows, directory)
    if group == "ablation": plot_ablation(rows, directory)
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
    mp.freeze_support()
    main()
