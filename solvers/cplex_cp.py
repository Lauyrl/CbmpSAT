"""IBM CPLEX CP Optimizer formulation for CBMP."""
from __future__ import annotations

import time

from .common import unavailable


def solve(instance, timeout: int) -> dict:
    try:
        from docplex.cp.model import CpoModel, all_diff, integer_var_list, abs as cp_abs, max as cp_max, min as cp_min, minimize
        from docplex.cp.config import context
    except ImportError:
        return unavailable("CPLEX CP")

    started = time.monotonic()

    context.solver.local.execfile = (
        r"C:\Program Files\IBM\ILOG\CPLEX_Studio222\cpoptimizer\bin\x64_win64\cpoptimizer.exe"
    )
    model = CpoModel()
    positions = integer_var_list(instance.n, 0, instance.n - 1, "p")
    model.add(all_diff(positions))

    distances = [
        cp_min(cp_abs(positions[u] - positions[v]), instance.n - cp_abs(positions[u] - positions[v]))
        for u, v in instance.edges
    ]
    bandwidth = cp_max(distances)
    model.add(minimize(bandwidth))
    encoding_time = time.monotonic() - started

    try:
        solution = model.solve(TimeLimit=max(0.01, timeout - encoding_time), LogVerbosity="Quiet")
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

    state = str(solution.get_solve_status()).upper()
    ub = int(solution.get_objective_values()[0]) if "FEASIBLE" in state or "OPTIMAL" in state else None
    return {
        "status": "OPTIMAL" if "OPTIMAL" in state else "TIMEOUT" if ub is not None else "ERROR",
        "best_ub": ub,
        "encoding_time": encoding_time,
        "solve_time": time.monotonic() - started - encoding_time,
        "variables": None,
        "clauses": None,
        "message": state,
    }
