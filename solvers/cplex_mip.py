"""IBM CPLEX MIP formulation for CBMP."""
from __future__ import annotations

import time

from .common import unavailable


def solve(instance, timeout: int) -> dict:
    try:
        from docplex.mp.model import Model
    except ImportError:
        return unavailable("CPLEX MIP")

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
        return {
            "status": "ERROR",
            "best_ub": None,
            "encoding_time": encoding_time,
            "solve_time": time.monotonic() - started - encoding_time,
            "variables": None,
            "clauses": None,
            "message": repr(error),
        }

    state = str(model.solve_details.status).upper()
    ub = int(solution.get_value(bandwidth)) if solution else None
    return {
        "status": "OPTIMAL" if "OPTIMAL" in state else "TIMEOUT" if ub is not None else "ERROR",
        "best_ub": ub,
        "encoding_time": encoding_time,
        "solve_time": model.solve_details.time,
        "variables": None,
        "clauses": None,
        "message": state,
    }
