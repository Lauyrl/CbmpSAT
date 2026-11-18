def unavailable(method: str) -> dict:
    return {
        "status": "UNAVAILABLE",
        "best_ub": None,
        "encoding_time": 0.0,
        "solve_time": 0.0,
        "variables": None,
        "clauses": None,
        "message": f"{method} is not installed",
    }
