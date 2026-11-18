"""Command-line entry point for one CBMP SAT solve."""
import argparse

from cbmp import SatConfig, load_instance, solve_timed


def main(dataset: str, use_symmetry_break: bool, use_heuristic_initial_ub: bool, timeout: float):
    config = SatConfig(
        symmetry="reflection" if use_symmetry_break else "none",
        heuristic=use_heuristic_initial_ub,
    )
    result = solve_timed(load_instance(dataset), config, timeout)
    if result.status == "OPTIMAL":
        print("minimum bandwidth:", result.best_ub)
    elif result.status == "TIMEOUT":
        print("timeout, lowest bandwidth found:", result.best_ub)
    else:
        print(result.status.lower(), result.message or "")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", help="name of .mtx file in datasets/")
    parser.add_argument("--timeout", type=float, default=600, help="time limit in seconds")
    parser.add_argument("--symmetry-break", action="store_true", help="add rotation + reflection symmetry breaking")
    parser.add_argument("--heuristic-ub", action="store_true", help="use Cuthill-McKee initial upper bound")
    args = parser.parse_args()
    main(args.dataset, args.symmetry_break, args.heuristic_ub, args.timeout)
