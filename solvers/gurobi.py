"""Gurobi MIP formulation for CBMP."""
from __future__ import annotations

import time

from .common import unavailable


def solve(instance, timeout: int) -> dict:
    try:
        import gurobipy as gp
    except ImportError:
        return unavailable("Gurobi")

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
        return {
            "status": "ERROR",
            "best_ub": None,
            "encoding_time": time.monotonic() - started,
            "solve_time": 0.0,
            "variables": None,
            "clauses": None,
            "message": repr(error),
        }

    ub = int(round(bandwidth.X)) if model.SolCount else None
    outcome = "OPTIMAL" if model.Status == gp.GRB.OPTIMAL else "TIMEOUT" if ub is not None else "ERROR"
    return {
        "status": outcome,
        "best_ub": ub,
        "encoding_time": encoding_time,
        "solve_time": model.Runtime,
        "variables": None,
        "clauses": None,
        "message": str(model.Status),
    }
