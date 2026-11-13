"""Compatibility entry point for Lauyrl/CbmpSAT.

The upstream repository runs experiments via ``python run_experiments.py``.
The experiment infrastructure now lives in ``experiments/run_experiments.py``;
this shim forwards all CLI arguments there unchanged.
"""
import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    script = Path(__file__).resolve().parent / "experiments" / "run_experiments.py"
    sys.argv[0] = str(script)
    runpy.run_path(str(script), run_name="__main__")

