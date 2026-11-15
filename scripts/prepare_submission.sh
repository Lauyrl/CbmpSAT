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
PYTHON="\${PYTHON:-python3}"
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
for directory in (Path("results/tables"), Path("results/figures")):
    if not directory.is_dir(): print(f"[WARN] Derived output directory is absent: {directory}")
PY
echo
echo "[DONE] Preflight completed. Review any [WARN] messages before submission."
git status --short
