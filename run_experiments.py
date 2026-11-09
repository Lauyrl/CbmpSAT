import csv
import multiprocessing as mp
from main import *

# === CONFIGURATION
# for default run
DATASETS = [
    "30_bus",
    "494_bus"
]

ABLATION_DATASETS = [
    "30_bus",
    "494_bus"
]

TIMEOUT = 60
OUTPUT_CSV = "results/experiment_results.csv"

def run_experiments():
    experiments = []

    # === DEFAULT EXPERIMENTS
    for dataset in DATASETS:
        experiments.append((dataset, True, True, "product"))

    # === ABLATION EXPERIMENTS
    for dataset in ABLATION_DATASETS:
        for symmetry_break in [False, True]:
            for heuristic_initial_ub in [False, True]:
                for eo_encoding in ["product",]: # "pairwise", 
                    experiments.append((dataset, symmetry_break, heuristic_initial_ub, eo_encoding))

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "dataset",
            "use_symmetry_break",
            "use_heuristic_initial_ub",
            "eo_encoding",
            "UB",
            "solve_time",
        ])
        writer.writeheader()

        for dataset, symmetry_break, heuristic_initial_ub, eo_encoding in experiments:
            print(f"\n=== {dataset} | symmetry={symmetry_break} | heuristic={heuristic_initial_ub} | EO={eo_encoding}")

            ub, solve_time = main(dataset, symmetry_break, heuristic_initial_ub, eo_encoding, TIMEOUT)

            writer.writerow({
                "dataset": dataset,
                "use_symmetry_break": symmetry_break,
                "use_heuristic_initial_ub": heuristic_initial_ub,
                "eo_encoding": eo_encoding,
                "UB": ub,
                "solve_time": f"{solve_time:.6f}",
            })
            f.flush()

if __name__ == "__main__":
    run_experiments()
