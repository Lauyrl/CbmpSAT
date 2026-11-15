#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "[ERROR] Not inside the CBMP Git repository."; exit 2; }
cd "$ROOT"
BRANCH="$(git branch --show-current)"
COMMIT="$(git rev-parse HEAD)"
if [[ -z "$BRANCH" ]]; then echo "[ERROR] Detached HEAD; switch to a named working branch before submission checks."; exit 2; fi
echo "== CBMP submission preflight =="
echo "Repository: $ROOT"
echo "Branch:     $BRANCH"
echo "Commit:     $COMMIT"
PYTHON="${PYTHON:-python3}"
"$PYTHON" - <<'PY'
import sys
print(f"Python: {sys.version.split()[0]}")
if sys.version_info < (3, 10): raise SystemExit("Python >= 3.10 is required.")
PY
echo
echo "== 1/5 Whitespace check =="
git diff --check
echo
echo "== 2/5 Dataset integrity =="
"$PYTHON" scripts/check_datasets.py
echo
echo "== 3/5 Automated tests (excluding explicitly slow tests) =="
"$PYTHON" -m pytest -q -m "not slow"
echo
echo "== 4/5 Report build =="
if command -v latexmk >/dev/null 2>&1; then
  (cd report && latexmk -pdf -interaction=nonstopmode -halt-on-error report.tex)
elif command -v pdflatex >/dev/null 2>&1; then
  (cd report && pdflatex -interaction=nonstopmode -halt-on-error report.tex && pdflatex -interaction=nonstopmode -halt-on-error report.tex)
else echo "[WARN] latexmk/pdflatex not installed; report build skipped."; fi
echo
echo "== 5/5 Current benchmark snapshot =="
"$PYTHON" - <<'PY'
import json
from pathlib import Path
runs_path, env_path = Path("results/runs.jsonl"), Path("results/env.json")
if not runs_path.is_file() or runs_path.stat().st_size == 0: raise SystemExit("[BLOCKER] results/runs.jsonl is missing or empty.")
if not env_path.is_file() or env_path.stat().st_size == 0: raise SystemExit("[BLOCKER] results/env.json is missing or empty.")
count, statuses = 0, {}
for line_no, line in enumerate(runs_path.read_text(encoding="utf-8").splitlines(), 1):
    if not line.strip(): continue
    try: record = json.loads(line)
    except json.JSONDecodeError as exc: raise SystemExit(f"Invalid JSONL at {runs_path}:{line_no}: {exc}")
    if not isinstance(record, dict): raise SystemExit(f"Expected JSON object at {runs_path}:{line_no}")
    status = str(record.get("status", "UNKNOWN")).upper()
    statuses[status] = statuses.get(status, 0) + 1
    count += 1
if count == 0: raise SystemExit("[BLOCKER] results/runs.jsonl contains no records.")
try: env = json.loads(env_path.read_text(encoding="utf-8"))
except json.JSONDecodeError as exc: raise SystemExit(f"Invalid JSON metadata at {env_path}: {exc}")
if not isinstance(env, dict): raise SystemExit("results/env.json must contain a JSON object.")
source_commit, dirty = str(env.get("git_commit", "")), env.get("git_dirty")
print(f"[OK] {count} JSONL records; statuses={statuses}")
print(f"[INFO] Snapshot source commit: {source_commit or 'not recorded'}")
if dirty is True or source_commit.endswith("-dirty"): print("[WARN] Snapshot was produced from a dirty working tree; treat it as exploratory, not reproducible.")
elif dirty is False: print("[OK] Metadata explicitly records git_dirty=false.")
else: print("[WARN] Metadata does not explicitly establish a clean working tree.")
required_tables = (
    Path("results/tables/table_encoding_comparison.csv"),
    Path("results/tables/table_encoding_comparison_pairs.csv"),
    Path("results/tables/table_exact_solvers.csv"),
    Path("results/tables/table_solvers_medium.csv"),
)
for table in required_tables:
    if not table.is_file() or table.stat().st_size == 0:
        raise SystemExit(f"[BLOCKER] Required current-snapshot table is missing or empty: {table}")
    print(f"[OK] Current result table present: {table}")

# Regenerate the four deterministic CSVs from the tracked raw snapshot in a
# temporary directory and require an exact match with committed artifacts.
import subprocess
import tempfile
with tempfile.TemporaryDirectory(prefix="cbmp-table-audit-") as tmp:
    subprocess.run(
        [sys.executable, "analysis/make_tables.py", "results/runs.jsonl", "--output-dir", tmp],
        check=True,
    )
    generated = (
        "table_encoding_comparison.csv",
        "table_encoding_comparison_pairs.csv",
        "table_exact_solvers.csv",
        "table_solvers_medium.csv",
    )
    for name in generated:
        expected = Path("results/tables") / name
        actual = Path(tmp) / name
        if not actual.is_file():
            raise SystemExit(f"[BLOCKER] Table generator did not create {name}")
        if expected.read_bytes() != actual.read_bytes():
            raise SystemExit(
                f"[BLOCKER] {expected} differs from regenerated output based on results/runs.jsonl"
            )
        print(f"[OK] {name} matches regenerated current-snapshot output")

if not Path("results/figures").is_dir():
    print("[INFO] results/figures/ will be created by analysis/make_plots.py")
PY
echo
echo "[DONE] Preflight completed. Review any [WARN] messages before submission."
git status --short
