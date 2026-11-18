"""Reproducible experiment runner for the Harwell--Boeing CBMP instances.

Each invocation writes checkpointed JSONL and a CSV under a separate results
subdirectory.  Re-running a command skips completed settings unless --force is
given, so an interrupted multi-hour batch can safely be resumed.
"""
from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from pysat.solvers import Cadical195
from scipy.io import mmread
from scipy.sparse.csgraph import reverse_cuthill_mckee

from alo_amo_eo_encodings import exactly_one as encode_exactly_one
from sat_encodings import (
    biconditional_X_and_G,
    break_reflection_symmetry,
    break_reflection_symmetry_direct,
    break_rotation_symmetry,
    direct_cyclic_edge,
    direct_edge_clause_count,
    injectivity_surjectivity_X,
    lower_upper_bound_G,
    monotonic_G,
    cyclic_edge,
)

DATASETS = Path(__file__).with_name("datasets")
EXEMPLARS = ("dwt_234", "impcol_d", "bcsstk06", "494_bus", "662_bus", "can_715")
LARGE = ("494_bus", "662_bus", "can_715")
MAX_DIRECT_CLAUSES = 25_000_000


@dataclass
class Instance:
    name: str
    n: int
    edges: list[tuple[int, int]]
    graph: object


def canonical(name: str) -> str:
    return name.replace(".mtx", "").replace("_", "")


def display_name(name: str) -> str:
    return re.sub(r"_+", "_", name.removesuffix(".mtx"))


def instance_path(name: str) -> Path:
    target = canonical(name)
    for path in DATASETS.glob("*.mtx"):
        if canonical(path.stem) == target:
            return path
    raise FileNotFoundError(f"no MatrixMarket file for {name!r} in {DATASETS}")


def load_instance(name: str) -> Instance:
    path = instance_path(name)
    graph = mmread(path).tocsr()
    rows, cols = graph.nonzero()
    edges = [(int(u), int(v)) for u, v in zip(rows, cols) if u < v]
    return Instance(name, graph.shape[0], edges, graph)


def lower_bounds() -> dict[str, int]:
    with (DATASETS / "lb.csv").open(newline="") as stream:
        return {canonical(row["instance"]): int(row["lb"]) for row in csv.DictReader(stream)}


def known_lb(name: str) -> int | None:
    return lower_bounds().get(canonical(name))


def cyclic_bandwidth(n: int, edges: Iterable[tuple[int, int]], assignment) -> int:
    return max(min(abs(assignment[u] - assignment[v]), n - abs(assignment[u] - assignment[v])) for u, v in edges)


def heuristic_upper_bound(instance: Instance) -> int:
    permutation = reverse_cuthill_mckee(instance.graph, symmetric_mode=False)
    assignment = np.empty(instance.n, dtype=int)
    assignment[permutation] = np.arange(instance.n)
    return int(cyclic_bandwidth(instance.n, instance.edges, assignment))


def make_sat_formula(instance: Instance, distance: str, eo_encoding: str, symmetry: str):
    """Build reusable assignment constraints and return an incremental edge adder."""
    n = instance.n
    x_start = 1
    X = [[x_start + vertex * n + label for label in range(n)] for vertex in range(n)]
    next_var = x_start + n * n
    clauses: list[list[int]] = []

    if distance == "direct":
        # Direct variables need both vertex and label exactly-one constraints.
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
            if initial_clause_count is None:
                initial_clause_count = clause_count
            satisfiable = solver.solve()
            if not satisfiable:
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
    except Exception as error:  # preserve a usable checkpoint when a backend fails
        queue.put({"status": "ERROR", "best_ub": incumbent.value if incumbent.value >= 0 else None,
                   "encoding_time": None, "solve_time": None, "variables": None, "clauses": None,
                   "message": repr(error)})


def run_sat_timed(instance: Instance, timeout: int, **options) -> dict:
    """Isolate each run so every PySAT backend has a reliable hard time limit."""
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


def unavailable(method: str) -> dict:
    return {"status": "UNAVAILABLE", "best_ub": None, "encoding_time": 0.0, "solve_time": 0.0,
            "variables": None, "clauses": None, "message": f"{method} is not installed"}


def run_external(method: str, instance: Instance, timeout: int) -> dict:
    if method == "CP-SAT":
        try:
            from ortools.sat.python import cp_model
        except ImportError:
            return unavailable(method)
        started = time.monotonic()
        model = cp_model.CpModel()
        positions = [model.NewIntVar(0, instance.n - 1, f"p_{vertex}") for vertex in range(instance.n)]
        model.AddAllDifferent(positions)
        distances = []
        for edge, (u, v) in enumerate(instance.edges):
            difference = model.NewIntVar(0, instance.n - 1, f"d_{edge}")
            complement = model.NewIntVar(1, instance.n, f"c_{edge}")
            distance = model.NewIntVar(0, instance.n // 2, f"cd_{edge}")
            model.AddAbsEquality(difference, positions[u] - positions[v])
            model.Add(complement == instance.n - difference)
            model.AddMinEquality(distance, [difference, complement])
            distances.append(distance)
        bandwidth = model.NewIntVar(0, instance.n // 2, "bandwidth")
        model.AddMaxEquality(bandwidth, distances)
        model.Minimize(bandwidth)
        encoding_time = time.monotonic() - started
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = max(0.01, timeout - encoding_time)
        status = solver.Solve(model)
        status_name = solver.StatusName(status)
        if status_name == "OPTIMAL":
            outcome = "OPTIMAL"
        elif status_name in {"FEASIBLE", "UNKNOWN"}:
            outcome = "TIMEOUT"
        else:
            outcome = "ERROR"
        ub = int(solver.Value(bandwidth)) if status_name in {"OPTIMAL", "FEASIBLE"} else None
        return {"status": outcome, "best_ub": ub, "encoding_time": encoding_time,
                "solve_time": solver.WallTime(), "variables": None, "clauses": None,
                "message": status_name}
    if method == "CPLEX CP":
        try:
            from docplex.cp.model import CpoModel, all_diff, integer_var_list, max as cp_max, min as cp_min, minimize
        except ImportError:
            return unavailable(method)
        started = time.monotonic()
        model = CpoModel()
        positions = integer_var_list(instance.n, 0, instance.n - 1, "p")
        model.add(all_diff(positions))
        distances = [cp_min(abs(positions[u] - positions[v]), instance.n - abs(positions[u] - positions[v]))
                     for u, v in instance.edges]
        bandwidth = cp_max(distances)
        model.add(minimize(bandwidth))
        encoding_time = time.monotonic() - started
        try:
            solution = model.solve(TimeLimit=max(0.01, timeout - encoding_time), LogVerbosity="Quiet")
        except Exception as error:
            return {"status": "ERROR", "best_ub": None, "encoding_time": encoding_time,
                    "solve_time": time.monotonic() - started - encoding_time, "variables": None, "clauses": None,
                    "message": repr(error)}
        state = str(solution.get_solve_status()).upper()
        ub = int(solution.get_value(bandwidth)) if "FEASIBLE" in state or "OPTIMAL" in state else None
        return {"status": "OPTIMAL" if "OPTIMAL" in state else "TIMEOUT" if ub is not None else "ERROR",
                "best_ub": ub, "encoding_time": encoding_time,
                "solve_time": time.monotonic() - started - encoding_time, "variables": None, "clauses": None,
                "message": state}
    elif method == "CPLEX MIP":
        try:
            from docplex.mp.model import Model
        except ImportError:
            return unavailable(method)
        started = time.monotonic()
        model = Model("cbmp")
        n = instance.n
        labels = model.binary_var_matrix(n, n, "x")
        positions = model.integer_var_list(n, lb=0, ub=n - 1, name="p")
        for vertex in range(n):
            model.add(model.sum(labels[vertex, label] for label in range(n)) == 1)
            model.add(positions[vertex] == model.sum(label * labels[vertex, label] for label in range(n)))
        for label in range(n):
            model.add(model.sum(labels[vertex, label] for vertex in range(n)) == 1)
        bandwidth = model.integer_var(lb=0, ub=n // 2, name="bandwidth")
        for edge, (u, v) in enumerate(instance.edges):
            difference = model.integer_var(lb=0, ub=n - 1, name=f"d_{edge}")
            direction = model.binary_var(name=f"sign_{edge}")
            branch = model.binary_var(name=f"arc_{edge}")
            model.add(difference >= positions[u] - positions[v])
            model.add(difference >= positions[v] - positions[u])
            model.add(difference <= positions[u] - positions[v] + n * direction)
            model.add(difference <= positions[v] - positions[u] + n * (1 - direction))
            model.add(bandwidth >= difference - n * branch)
            model.add(bandwidth >= n - difference - n * (1 - branch))
        model.minimize(bandwidth)
        encoding_time = time.monotonic() - started
        try:
            solution = model.solve(log_output=False, TimeLimit=max(0.01, timeout - encoding_time))
        except Exception as error:
            return {"status": "ERROR", "best_ub": None, "encoding_time": encoding_time,
                    "solve_time": time.monotonic() - started - encoding_time, "variables": None, "clauses": None,
                    "message": repr(error)}
        state = str(model.solve_details.status).upper()
        ub = int(solution.get_value(bandwidth)) if solution else None
        return {"status": "OPTIMAL" if "OPTIMAL" in state else "TIMEOUT" if ub is not None else "ERROR",
                "best_ub": ub, "encoding_time": encoding_time,
                "solve_time": model.solve_details.time, "variables": None, "clauses": None, "message": state}
    elif method == "Gurobi":
        try:
            import gurobipy as gp
        except ImportError:
            return unavailable(method)
        started = time.monotonic()
        try:
            model = gp.Model("cbmp")
            model.Params.OutputFlag = 0
            n = instance.n
            labels = model.addVars(n, n, vtype=gp.GRB.BINARY, name="x")
            positions = model.addVars(n, vtype=gp.GRB.INTEGER, lb=0, ub=n - 1, name="p")
            for vertex in range(n):
                model.addConstr(labels.sum(vertex, "*") == 1)
                model.addConstr(positions[vertex] == gp.quicksum(label * labels[vertex, label] for label in range(n)))
            for label in range(n):
                model.addConstr(labels.sum("*", label) == 1)
            bandwidth = model.addVar(vtype=gp.GRB.INTEGER, lb=0, ub=n // 2, name="bandwidth")
            for edge, (u, v) in enumerate(instance.edges):
                delta = model.addVar(lb=-(n - 1), ub=n - 1, name=f"delta_{edge}")
                difference = model.addVar(lb=0, ub=n - 1, name=f"d_{edge}")
                complement = model.addVar(lb=1, ub=n, name=f"c_{edge}")
                distance = model.addVar(lb=0, ub=n // 2, name=f"cd_{edge}")
                model.addConstr(delta == positions[u] - positions[v])
                model.addGenConstrAbs(difference, delta)
                model.addConstr(complement == n - difference)
                model.addGenConstrMin(distance, [difference, complement])
                model.addConstr(bandwidth >= distance)
            model.setObjective(bandwidth, gp.GRB.MINIMIZE)
            encoding_time = time.monotonic() - started
            model.Params.TimeLimit = max(0.01, timeout - encoding_time)
            model.optimize()
        except Exception as error:
            return {"status": "ERROR", "best_ub": None, "encoding_time": time.monotonic() - started,
                    "solve_time": 0.0, "variables": None, "clauses": None, "message": repr(error)}
        ub = int(round(bandwidth.X)) if model.SolCount else None
        outcome = "OPTIMAL" if model.Status == gp.GRB.OPTIMAL else "TIMEOUT" if ub is not None else "ERROR"
        return {"status": outcome, "best_ub": ub, "encoding_time": encoding_time,
                "solve_time": model.Runtime, "variables": None, "clauses": None, "message": str(model.Status)}
    raise ValueError(f"unknown external method: {method}")


def record_base(group: str, instance: Instance, method: str, result: dict, **settings) -> dict:
    lb = known_lb(instance.name)
    ub = result.get("best_ub")
    return {"group": group, "instance": instance.name, "method": method, "n": instance.n,
            "edges": len(instance.edges), "known_lb": lb, "gap": None if ub is None or lb is None else ub - lb,
            **settings, **result}


def completed_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {json.loads(line)["key"] for line in path.read_text().splitlines() if line.strip()}


def write_record(path: Path, record: dict):
    with path.open("a", encoding="utf8") as stream:
        stream.write(json.dumps(record, default=str) + "\n")
        stream.flush()


def export_csv(records_path: Path, output: Path):
    rows = [json.loads(line) for line in records_path.read_text().splitlines() if line.strip()]
    keys = sorted({key for row in rows for key in row if key not in {"incumbents", "key"}})
    with output.open("w", newline="", encoding="utf8") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows({key: value for key, value in row.items() if key in keys} for row in rows)
    return rows


def plot_encoding(rows: list[dict], directory: Path):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return
    pairs = [row for row in rows if row["group"] == "encodings"]
    figure, axis = plt.subplots()
    for method, style in (("direct", "o-"), ("order", "s-")):
        points = sorted((row["n"], row["clauses"] / row["edges"]) for row in pairs
                        if row["method"] == method and row["exactly_one"] == "product"
                        and row["status"] != "ENCODING_FAILED")
        if points:
            axis.plot(*zip(*points), style, label=f"{method} measured")
    analytical = sorted((row["n"], row["clauses"] / row["edges"]) for row in pairs
                        if row["method"] == "direct" and row["exactly_one"] == "product"
                        and row["status"] == "ENCODING_FAILED")
    if analytical:
        axis.plot(*zip(*analytical), "k--", label="direct analytical")
    axis.set(xlabel="N", ylabel="clauses per edge", yscale="log")
    axis.legend()
    figure.tight_layout()
    figure.savefig(directory / "clauses_per_edge.png", dpi=180)
    plt.close(figure)

    figure, axis = plt.subplots()
    timed = [row for row in pairs if row["status"] != "ENCODING_FAILED" and row["encoding_time"] is not None]
    labels = [f"{row['instance']}\n{row['method']}" for row in timed]
    times = [row["encoding_time"] + row["solve_time"] for row in timed]
    axis.bar(range(len(times)), times)
    axis.set(xticks=range(len(times)), xticklabels=labels, ylabel="time (s)")
    axis.tick_params(axis="x", labelrotation=70)
    figure.tight_layout()
    figure.savefig(directory / "times.png", dpi=180)
    plt.close(figure)


def plot_incumbents(rows: list[dict], directory: Path):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return
    figure, axis = plt.subplots()
    for row in rows:
        values = row.get("incumbents", [])
        if values:
            axis.step([0] + [point["elapsed"] for point in values], [values[0]["ub"]] + [point["ub"] for point in values], where="post", label=f"{row['instance']} / {row['method']}")
    axis.set(xlabel="elapsed time, including encoding (s)", ylabel="best UB")
    axis.legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(directory / "ub_vs_time.png", dpi=180)
    plt.close(figure)


def plot_ablation(rows: list[dict], directory: Path):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return
    levels = ("weak", "medium", "strong")
    instances = sorted({row["instance"] for row in rows})
    figure, axes = plt.subplots(1, len(instances), figsize=(4 * len(instances), 3), squeeze=False)
    for axis, name in zip(axes[0], instances):
        values = {row.get("level"): row for row in rows if row["instance"] == name}
        times = [(values[level]["encoding_time"] or 0) + (values[level]["solve_time"] or 0)
                 if level in values else 0 for level in levels]
        axis.bar(levels, times)
        axis.set(title=name, ylabel="time (s)")
    figure.tight_layout()
    figure.savefig(directory / "per_level_times.png", dpi=180)
    plt.close(figure)


def run_group(group: str, datasets: list[str], timeout: int, output: Path, force: bool):
    directory = output / group
    directory.mkdir(parents=True, exist_ok=True)
    records_path = directory / "records.jsonl"
    done = set() if force else completed_keys(records_path)
    methods = (["SAT", "CP-SAT", "CPLEX CP", "CPLEX MIP", "Gurobi"] if group == "methods" else [])
    if group == "encodings":
        # Product is held fixed for distance; order is held fixed for EO.
        settings = [("direct", "product"), ("order", "product"), ("order", "pairwise")]
    elif group == "ub-time":
        settings = [("order", "product")]
    elif group == "ablation":
        settings = [("weak", "product"), ("medium", "product"), ("strong", "product"),
                    ("no_rotation", "product"), ("no_reflection", "product"), ("no_heuristic", "product")]
    else:
        settings = []

    for name in datasets:
        instance = load_instance(name)
        if group == "methods":
            jobs = [(method, {}) for method in methods]
        elif group == "encodings":
            jobs = [(distance, {"distance": distance, "exactly_one": eo}) for distance, eo in settings]
        elif group == "ub-time":
            jobs = [("SAT", {"distance": "order", "exactly_one": "product"})]
        else:
            jobs = [(level, {"level": level}) for level, _ in settings]
        for method, config in jobs:
            key = json.dumps([name, method, config], sort_keys=True)
            if key in done:
                continue
            if method == "SAT" or group in {"encodings", "ub-time", "ablation"}:
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
                result = run_external(method, instance, timeout)
            record = record_base(group, instance, method, result, timeout_seconds=timeout, **config)
            record["key"] = key
            write_record(records_path, record)
    rows = export_csv(records_path, directory / "results.csv")
    if group == "encodings": plot_encoding(rows, directory)
    if group == "ub-time": plot_incumbents(rows, directory)
    if group == "ablation": plot_ablation(rows, directory)
    return rows


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("group", choices=("methods", "encodings", "ub-time", "ablation", "all"))
    parser.add_argument("--timeout", type=int, default=1200, help="per-setting wall-clock limit in seconds (default: 20 min)")
    parser.add_argument("--output", type=Path, default=Path("results"))
    parser.add_argument("--datasets", nargs="*", help="override the group's default instances")
    parser.add_argument("--force", action="store_true", help="run settings even when a completed checkpoint exists")
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
