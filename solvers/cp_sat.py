"""OR-Tools CP-SAT formulation for CBMP."""
from __future__ import annotations

import time

from .common import unavailable


def solve(instance, timeout: int) -> dict:
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return unavailable("CP-SAT")

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
    return {
        "status": outcome,
        "best_ub": ub,
        "encoding_time": encoding_time,
        "solve_time": solver.WallTime(),
        "variables": None,
        "clauses": None,
        "message": status_name,
    }
