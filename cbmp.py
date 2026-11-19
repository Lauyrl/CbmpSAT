"""SAT models and execution helpers for the cyclic bandwidth minimization problem."""
from __future__ import annotations

import multiprocessing as mp
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
from pysat.solvers import Glucose4, Cadical195
from scipy.io import mmread
from scipy.sparse.csgraph import reverse_cuthill_mckee

from alo_amo_eo_encodings import exactly_one
from helper.helper import find_instance_path
from sat_encodings import (
    biconditional_X_and_G,
    break_reflection_symmetry,
    break_reflection_symmetry_direct,
    break_rotation_symmetry,
    cyclic_edge,
    direct_cyclic_edge,
    direct_edge_clause_count,
    injectivity_surjectivity_X,
    lower_upper_bound_G,
    monotonic_G,
)

DATASETS = Path(__file__).with_name("datasets")
MAX_DIRECT_CLAUSES = 25_000_000


@dataclass
class Instance:
    name: str
    n: int
    edges: list[tuple[int, int]]
    graph: object


@dataclass(frozen=True)
class SatConfig:
    distance: str = "order"
    exactly_one: str = "commander"
    symmetry: str = "none"
    heuristic: bool = False


@dataclass
class SatResult:
    status: str
    best_ub: int | None
    encoding_time: float | None
    solve_time: float | None
    variables: int | None
    clauses: int | None
    incumbents: list[dict] = field(default_factory=list)
    message: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def load_instance(name: str) -> Instance:
    matrix = mmread(find_instance_path(DATASETS, name)).tocsr()
    pattern = (matrix != 0).astype(np.int8)
    graph = ((pattern + pattern.T) != 0).astype(np.int8).tocsr()
    rows, cols = graph.nonzero()
    edges = [(int(u), int(v)) for u, v in zip(rows, cols) if u < v]
    return Instance(name, graph.shape[0], edges, graph)


def compute_cyclic_bandwidth(n: int, edges: Iterable[tuple[int, int]], assignment) -> int:
    return max(min(abs(assignment[u] - assignment[v]), n - abs(assignment[u] - assignment[v])) for u, v in edges)


def cuthill_mckee_layout(graph, n: int):
    permutation = reverse_cuthill_mckee(graph.tocsr(), symmetric_mode=False)
    assignment = np.empty(n, dtype=int)
    assignment[permutation] = np.arange(n)
    return assignment


def initial_upper_bound(instance: Instance, heuristic: bool) -> int:
    if not heuristic:
        return instance.n // 2 + 1
    assignment = cuthill_mckee_layout(instance.graph, instance.n)
    return int(compute_cyclic_bandwidth(instance.n, instance.edges, assignment))


def make_sat_formula(instance: Instance, config: SatConfig):
    """Build reusable SAT constraints and return an incremental edge encoder."""
    n = instance.n
    X = [[1 + u * n + i for i in range(n)] for u in range(n)]
    next_var = 1 + n * n
    clauses: list[list[int]] = []

    if config.distance == "direct":
        for u in range(n):
            new_clauses, next_var = exactly_one(X[u], next_var, config.exactly_one)
            clauses.extend(new_clauses)
        for i in range(n):
            new_clauses, next_var = exactly_one([X[u][i] for u in range(n)], next_var, config.exactly_one)
            clauses.extend(new_clauses)
        G = None
    elif config.distance == "order":
        g_start = next_var
        G = [[g_start + u * (n + 1) + i for i in range(n + 1)] for u in range(n)]
        next_var = g_start + n * (n + 1)
        new_clauses, next_var = injectivity_surjectivity_X(n, X, next_var, config.exactly_one)
        clauses.extend(new_clauses)
        clauses.extend(monotonic_G(n, G))
        clauses.extend(lower_upper_bound_G(n, G))
        clauses.extend(biconditional_X_and_G(n, X, G))
    else:
        raise ValueError(f"unknown distance encoding: {config.distance}")

    if config.symmetry in {"rotation", "reflection"}:
        clauses.extend(break_rotation_symmetry(X, 0))
    if config.symmetry == "reflection":
        clauses.extend(break_reflection_symmetry_direct(n, X) if config.distance == "direct"
                       else break_reflection_symmetry(n, X, G))

    def add_edge_constraints(solver, upper_bound: int) -> int:
        count = 0
        for u, v in instance.edges:
            edge_clauses = (direct_cyclic_edge(n, X, u, v, upper_bound) if config.distance == "direct"
                            else cyclic_edge(n, X, G, u, v, upper_bound))
            solver.append_formula(edge_clauses)
            count += len(edge_clauses)
        return count

    return clauses, next_var - 1, add_edge_constraints


def extract_assignment(model, n: int) -> list[int]:
    assignment = [0] * n
    for lit in model:
        if 0 < lit <= n * n:
            u, i = divmod(lit - 1, n)
            assignment[u] = i
    return assignment


def solve(instance: Instance | str, config: SatConfig = SatConfig(),
          checkpoint: Callable[[int, list[dict]], None] | None = None) -> SatResult:
    """Solve one CBMP instance, returning timings and every improving incumbent."""
    if isinstance(instance, str):
        instance = load_instance(instance)

    started = time.monotonic()
    upper_bound = initial_upper_bound(instance, config.heuristic)
    if config.distance == "direct":
        estimated = len(instance.edges) * direct_edge_clause_count(instance.n, upper_bound)
        if estimated > MAX_DIRECT_CLAUSES:
            return SatResult("ENCODING_FAILED", None, 0.0, 0.0, None, estimated,
                             message=f"estimated {estimated:,} direct clauses exceeds safety limit")

    clauses, variables, add_edge_constraints = make_sat_formula(instance, config)
    encoding_time = time.monotonic() - started
    solver = Cadical195()
    solver.append_formula(clauses)
    clause_count = len(clauses)
    initial_clause_count = None
    incumbents = []

    try:
        iteration = 0
        total_solve_time = 0.0

        while True:
            iteration += 1
            clause_count += add_edge_constraints(solver, upper_bound)
            initial_clause_count = initial_clause_count or clause_count

            t0 = time.monotonic()
            sat = solver.solve()
            solve_time = time.monotonic() - t0
            total_solve_time += solve_time

            print(
                f"[SAT {iteration}] bandwidth <= {upper_bound - 1}: "
                f"{'SAT' if sat else 'UNSAT'} | "
                f"solve={solve_time:.3f}s | "
                f"total={total_solve_time:.3f}s | "
                f"clauses={clause_count}",
                flush=True,
            )

            if not sat:
                return SatResult("OPTIMAL", upper_bound, encoding_time, time.monotonic() - started - encoding_time,
                                 variables, initial_clause_count, incumbents)

            assignment = extract_assignment(solver.get_model(), instance.n)
            new_upper_bound = compute_cyclic_bandwidth(instance.n, instance.edges, assignment)
            print(
                f"[SAT {iteration}] incumbent: {upper_bound} -> {new_upper_bound}",
                flush=True,
            )
            upper_bound = new_upper_bound
            incumbents.append({"elapsed": time.monotonic() - started, "ub": upper_bound})
            if checkpoint:
                checkpoint(upper_bound, incumbents)
    finally:
        solver.delete()


def _solve_worker(queue, shared_ub, instance: Instance, config: SatConfig):
    def checkpoint(upper_bound, _incumbents):
        shared_ub.value = upper_bound

    try:
        queue.put(solve(instance, config, checkpoint).as_dict())
    except Exception as error:
        queue.put(SatResult("ERROR", shared_ub.value if shared_ub.value >= 0 else None,
                            None, None, None, None, message=repr(error)).as_dict())


def solve_timed(instance: Instance, config: SatConfig, timeout: float) -> SatResult:
    """Apply a hard timeout in a child process for solvers without interruption support."""
    initial_ub = initial_upper_bound(instance, config.heuristic)
    shared_ub = mp.Value("i", initial_ub)
    queue = mp.Queue()
    process = mp.Process(target=_solve_worker, args=(queue, shared_ub, instance, config))
    started = time.monotonic()
    process.start()
    process.join(timeout)
    elapsed = time.monotonic() - started

    if process.is_alive():
        process.terminate()
        process.join()
        incumbents = [{"elapsed": 0.0, "ub": shared_ub.value}] if shared_ub.value >= 0 else []
        return SatResult("TIMEOUT", shared_ub.value if shared_ub.value >= 0 else None,
                         None, elapsed, None, None, incumbents)
    if not queue.empty():
        return SatResult(**queue.get())
    return SatResult("ERROR", None, None, elapsed, None, None,
                     message=f"worker exited with code {process.exitcode}")
