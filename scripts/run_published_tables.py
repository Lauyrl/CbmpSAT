#!/usr/bin/env python3
"""Run the 113-instance TSCB/ITPS/NILS benchmark and rebuild Tables 2 and 3.

The ITPS and NILS source repositories are not vendored here. TSCB is accepted as
a command template because its historical download page is no longer reachable.
See docs/REFERENCE_TABLE_REPRODUCTION.md for setup and command examples.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import warnings
from collections import defaultdict
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "results/tables/reference/benchmark_manifest.csv"
DEFAULT_RAW = ROOT / "results/tables/reproduced/benchmark_runs.csv"
FAMILY_ORDER = [
    "path", "cycle", "mesh2D", "mesh3D", "tree", "caterpillar",
    "hypercube", "Harwell-Boeing",
]
FAMILY_COUNTS = {
    "path": 15, "cycle": 15, "mesh2D": 15, "mesh3D": 10,
    "tree": 12, "caterpillar": 15, "hypercube": 3, "Harwell-Boeing": 28,
}
ALGORITHM_ORDER = ["TSCB", "ITPS", "NILS"]
RAW_FIELDS = [
    "instance", "family", "algorithm", "rep", "seed", "best_cost",
    "time_to_best", "status", "return_code", "outer_timeout",
]


def load_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 113:
        raise ValueError(f"Expected the 113-instance manifest; found {len(rows)} rows in {path}")
    names = [row["instance"] for row in rows]
    if len(set(names)) != len(names):
        raise ValueError("The benchmark manifest contains duplicate instance names")
    counts = {family: sum(row["family"] == family for row in rows) for family in FAMILY_ORDER}
    if counts != FAMILY_COUNTS:
        raise ValueError(f"Unexpected instance counts by family: {counts}")
    for row in rows:
        for target in ("stop_target", "error_target", "best_target"):
            if int(row[target]) <= 0:
                raise ValueError(f"Non-positive {target} for {row['instance']}")
    return rows


def read_known_result(path: Path) -> tuple[int, float]:
    """Read the final best-cost/time record written by the published ITPS/NILS code."""
    if not path.is_file():
        raise ValueError(f"Algorithm did not write its result record: {path}")
    records = []
    for line in path.read_text(errors="replace").splitlines():
        fields = line.split()
        if len(fields) < 3:
            continue
        try:
            cost = int(float(fields[1]))
            elapsed = float(fields[2])
        except (ValueError, OverflowError):
            continue
        if cost < 0 or not math.isfinite(elapsed) or elapsed < 0:
            continue
        records.append((cost, elapsed))
    if not records:
        raise ValueError(f"No valid best-cost/time rows in {path}")
    return records[-1]


def run_one(
    algorithm: str,
    item: dict[str, str],
    input_file: Path,
    rep: int,
    seed: int,
    args: argparse.Namespace,
    output_root: Path,
) -> dict[str, object]:
    run_dir = output_root / "work" / algorithm.lower() / item["instance"] / f"rep_{rep:02d}"
    run_dir.mkdir(parents=True, exist_ok=True)
    local_input = run_dir / item["source_file"]
    shutil.copyfile(input_file, local_input)
    # NILS writes INPUT + F + rep; ITPS writes INPUT + 2F + rep.
    result_suffix = f"2F{rep}" if algorithm == "ITPS" else f"F{rep}"
    # Pass the basename because the legacy C++ sources use a 100-byte input buffer.
    solver_input = local_input.name
    result_file = run_dir / f"{solver_input}{result_suffix}"
    result_file.unlink(missing_ok=True)
    stdout_path = run_dir / "stdout.txt"
    stderr_path = run_dir / "stderr.txt"

    if algorithm == "NILS":
        command = [
            str(args.nils_bin), "-i", solver_input, "--seed", str(seed),
            "-rep", str(rep), "-alb", item["stop_target"],
            "-L1", "100", "-L2", "20", "-L3", "2000", "-alpha", "0.84",
        ]
    elif algorithm == "ITPS":
        command = [
            str(args.itps_bin), "-i", solver_input, "--seed", str(seed),
            "-rep", str(rep), "-alb", item["stop_target"],
            "-pls", item["itps_pls"], "-pth", item["itps_pth"],
            "-prb", item["itps_prb"], "-prc", item["itps_prc"],
            "-tnf", item["itps_tnf"], "-dep", item["itps_dep"],
        ]
    else:
        if not args.tscb_command:
            raise ValueError("TSCB needs --tscb-command; its historical download page is unavailable")
        if not args.tscb_cost_regex or not args.tscb_time_regex:
            raise ValueError("TSCB needs --tscb-cost-regex and --tscb-time-regex for its output format")
        values = {
            "instance": solver_input,
            "name": item["instance"],
            "seed": str(seed),
            "rep": str(rep),
            "lower_bound": item["stop_target"],
            "time_limit": str(args.time_limit),
        }
        # Parse first, then substitute so paths with spaces stay one argument.
        command = [part.format(**values) for part in shlex.split(args.tscb_command)]

    outer_timeout = False
    try:
        completed = subprocess.run(
            command,
            cwd=run_dir,
            capture_output=True,
            text=True,
            timeout=args.time_limit + args.timeout_grace,
            check=False,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        return_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        outer_timeout = True
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        return_code = -9
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")

    if return_code != 0:
        raise RuntimeError(
            f"{algorithm} exited with status {return_code}; see {stdout_path} and {stderr_path}"
        )

    if algorithm in {"ITPS", "NILS"}:
        best_cost, time_to_best = read_known_result(result_file)
    else:
        output = stdout + "\n" + stderr
        cost_matches = re.findall(args.tscb_cost_regex, output, re.MULTILINE | re.IGNORECASE)
        time_matches = re.findall(args.tscb_time_regex, output, re.MULTILINE | re.IGNORECASE)
        if not cost_matches or not time_matches:
            raise ValueError(
                f"Could not parse TSCB best cost/time in rep {rep} for {item['instance']}; "
                f"see {stdout_path} and {stderr_path}"
            )
        best_cost = int(float(cost_matches[-1][0] if isinstance(cost_matches[-1], tuple) else cost_matches[-1]))
        time_to_best = float(time_matches[-1][0] if isinstance(time_matches[-1], tuple) else time_matches[-1])

    if best_cost < 0 or not math.isfinite(time_to_best) or time_to_best < 0:
        raise ValueError(f"Invalid parsed result for {algorithm}/{item['instance']}/rep {rep}")
    return {
        "instance": item["instance"],
        "family": item["family"],
        "algorithm": algorithm,
        "rep": rep,
        "seed": seed,
        "best_cost": best_cost,
        "time_to_best": time_to_best,
        "status": "ok",
        "return_code": return_code,
        "outer_timeout": int(outer_timeout),
    }


def append_record(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_FIELDS)
        if needs_header:
            writer.writeheader()
        writer.writerow(record)
        handle.flush()


def read_existing(path: Path) -> dict[tuple[str, str, int], dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    completed = {}
    for row in rows:
        if row.get("status") == "ok":
            completed[(row["instance"], row["algorithm"], int(row["rep"]))] = row
    return completed


def run_suite(manifest: list[dict[str, str]], args: argparse.Namespace) -> None:
    if not args.instances_dir:
        raise ValueError("Provide --instances-dir pointing to the extracted 113 .rnd files")
    instances_dir = Path(args.instances_dir).resolve()
    selected = [r for r in manifest if not args.family or r["family"] in args.family]
    if args.limit:
        selected = selected[: args.limit]
    missing = [r["source_file"] for r in selected if not (instances_dir / r["source_file"]).is_file()]
    if missing:
        preview = ", ".join(missing[:8])
        raise FileNotFoundError(f"Missing {len(missing)} benchmark files under {instances_dir}: {preview}")
    if "NILS" in args.algorithms and not args.nils_bin:
        raise ValueError("Provide --nils-bin for the NILS executable")
    if "ITPS" in args.algorithms and not args.itps_bin:
        raise ValueError("Provide --itps-bin for the ITPS executable")
    for option in ("nils_bin", "itps_bin"):
        binary = getattr(args, option)
        if binary:
            resolved = Path(binary).expanduser().resolve()
            if not resolved.is_file() or not os.access(resolved, os.X_OK):
                raise FileNotFoundError(f"--{option.replace('_', '-')} does not exist: {resolved}")
            setattr(args, option, str(resolved))
    if "TSCB" in args.algorithms:
        if not args.tscb_command:
            raise ValueError("Provide --tscb-command for TSCB")
        if not args.tscb_cost_regex or not args.tscb_time_regex:
            raise ValueError("Provide --tscb-cost-regex and --tscb-time-regex for TSCB")
        tscb_parts = shlex.split(args.tscb_command)
        if not tscb_parts:
            raise ValueError("--tscb-command is empty")
        tscb_executable = Path(tscb_parts[0]).expanduser()
        if tscb_executable.exists():
            resolved = tscb_executable.resolve()
            if not resolved.is_file() or not os.access(resolved, os.X_OK):
                raise FileNotFoundError(f"TSCB executable is not runnable: {resolved}")
            tscb_parts[0] = str(resolved)
        else:
            found = shutil.which(tscb_parts[0])
            if not found:
                raise FileNotFoundError(f"TSCB executable was not found: {tscb_parts[0]}")
            tscb_parts[0] = found
        template_values = {
            "instance": "instance.rnd", "name": "instance", "seed": "0",
            "rep": "0", "lower_bound": "1", "time_limit": "600",
        }
        try:
            [part.format(**template_values) for part in tscb_parts]
        except (KeyError, ValueError) as exc:
            raise ValueError(f"Invalid placeholder in --tscb-command: {exc}") from exc
        for option, pattern in (
            ("--tscb-cost-regex", args.tscb_cost_regex),
            ("--tscb-time-regex", args.tscb_time_regex),
        ):
            try:
                compiled = re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"Invalid {option}: {exc}") from exc
            if compiled.groups < 1:
                raise ValueError(f"{option} must contain a capture group for its value")
        args.tscb_command = shlex.join(tscb_parts)

    raw_path = Path(args.raw_csv).resolve()
    done = read_existing(raw_path)
    failures = 0
    for item in selected:
        input_file = instances_dir / item["source_file"]
        for algorithm in args.algorithms:
            for rep in range(args.reps):
                key = (item["instance"], algorithm, rep)
                if not args.overwrite and key in done:
                    continue
                seed = args.seed_start + rep
                print(f"[{algorithm}] {item['instance']} run {rep + 1}/{args.reps}", flush=True)
                try:
                    record = run_one(algorithm, item, input_file, rep, seed, args, raw_path.parent)
                except Exception as exc:  # keep the raw record auditable and continue the suite
                    failures += 1
                    record = {
                        "instance": item["instance"], "family": item["family"],
                        "algorithm": algorithm, "rep": rep, "seed": seed,
                        "best_cost": "", "time_to_best": "", "status": "failed",
                        "return_code": "", "outer_timeout": 0,
                    }
                    print(f"  FAILED: {exc}", file=sys.stderr, flush=True)
                append_record(raw_path, record)
                if record["status"] == "ok":
                    done[key] = {k: str(v) for k, v in record.items()}
    if failures:
        print(f"Saved raw output with {failures} failed runs at {raw_path}; tables not regenerated.", file=sys.stderr)
        return

    complete_matrix = (
        len(selected) == 113
        and len(args.algorithms) == 3
        and set(args.algorithms) == set(ALGORITHM_ORDER)
        and args.reps == 50
    )
    if not complete_matrix:
        print(f"Partial run saved at {raw_path}; run all 113 instances x 50 runs x 3 methods to generate Tables 2/3.")
        return
    aggregate(raw_path, manifest, Path(args.output_dir).resolve())


def read_raw(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def significance(a: list[int], b: list[int]) -> tuple[str, float, str]:
    """Apply the paper's Shapiro-Wilk/Bartlett/ANOVA-Welch/Kruskal procedure."""
    try:
        from scipy import stats
    except ImportError as exc:
        raise RuntimeError(
            "Install SciPy to aggregate Table 3: python3 -m pip install scipy"
        ) from exc
    if len(set(a)) == 1 and len(set(b)) == 1:
        if a[0] == b[0]:
            return "*", 1.0, "constant-equal"
        return ("+" if a[0] < b[0] else "-"), 0.0, "constant-different"
    # A constant sample is degenerate rather than normally distributed.
    if len(set(a)) == 1 or len(set(b)) == 1:
        pvalue = float(stats.kruskal(a, b).pvalue)
        test = "kruskal-wallis"
        if pvalue >= 0.05:
            return "*", pvalue, test
        return ("+" if mean(a) < mean(b) else "-"), pvalue, test
    normal_a = stats.shapiro(a).pvalue >= 0.05
    normal_b = stats.shapiro(b).pvalue >= 0.05
    if not (normal_a and normal_b):
        pvalue = float(stats.kruskal(a, b).pvalue)
        test = "kruskal-wallis"
    else:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            bartlett_p = float(stats.bartlett(a, b).pvalue)
        if bartlett_p >= 0.05:
            pvalue = float(stats.f_oneway(a, b).pvalue)
            test = "anova"
        else:
            pvalue = float(stats.ttest_ind(a, b, equal_var=False).pvalue)
            test = "welch-t"
    if not math.isfinite(pvalue) or pvalue >= 0.05:
        return "*", pvalue if math.isfinite(pvalue) else 1.0, test
    return ("+" if mean(a) < mean(b) else "-"), pvalue, test


def aggregate(raw_path: Path, manifest: list[dict[str, str]], output_dir: Path) -> None:
    raw = read_raw(raw_path)
    expected = {(r["instance"], a, rep) for r in manifest for a in ALGORITHM_ORDER for rep in range(50)}
    seen: dict[tuple[str, str, int], dict[str, str]] = {}
    for row in raw:
        key = (row["instance"], row["algorithm"], int(row["rep"]))
        if key in expected and row.get("status") == "ok":
            seen[key] = row
    missing = expected - set(seen)
    if missing:
        raise ValueError(f"Cannot regenerate tables: {len(missing)} of {len(expected)} runs are missing or failed")

    data: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in seen.values():
        data[(row["instance"], row["algorithm"])].append(row)
    metrics: dict[tuple[str, str], dict[str, float | int]] = {}
    for item in manifest:
        for algorithm in ALGORITHM_ORDER:
            runs = sorted(data[(item["instance"], algorithm)], key=lambda r: int(r["rep"]))
            costs = [int(r["best_cost"]) for r in runs]
            times = [float(r["time_to_best"]) for r in runs]
            target = int(item["error_target"])
            rmse = math.sqrt(mean(((cost - target) / target) ** 2 for cost in costs))
            metrics[(item["instance"], algorithm)] = {
                "avg_cost": mean(costs), "avg_time": mean(times), "rmse": rmse,
                "best_cost": min(costs),
                "is_best": int(min(costs) <= int(item["best_target"])),
            }

    table2_rows = []
    for family in FAMILY_ORDER:
        family_items = [r for r in manifest if r["family"] == family]
        if not family_items:
            continue
        row: dict[str, object] = {"Graph type": family, "Num.": len(family_items)}
        for algorithm in ALGORITHM_ORDER:
            vals = [metrics[(it["instance"], algorithm)] for it in family_items]
            for key, metric_name in [("Avg. Cbb", "avg_cost"), ("Avg. Tb", "avg_time"), ("O-RMSE", "rmse")]:
                row[f"{algorithm} {key}"] = mean(float(v[metric_name]) for v in vals)
            row[f"{algorithm} % Best"] = 100 * mean(int(v["is_best"]) for v in vals)
        table2_rows.append(row)

    wins = matches = fails = 0
    for item in manifest:
        nils = int(metrics[(item["instance"], "NILS")]["best_cost"])
        tscb = int(metrics[(item["instance"], "TSCB")]["best_cost"])
        if nils < tscb:
            wins += 1
        elif nils == tscb:
            matches += 1
        else:
            fails += 1
    table2_rows.append({
        "Graph type": "Win/Match/Fail", "Num.": f"{wins}/{matches}/{fails}",
        **{f"{a} {k}": "" for a in ALGORITHM_ORDER for k in ("Avg. Cbb", "Avg. Tb", "O-RMSE", "% Best")},
    })

    table3_rows = []
    for family in FAMILY_ORDER:
        items = [r for r in manifest if r["family"] == family]
        if not items:
            continue
        row: dict[str, object] = {"Graph type": family, "Num.": len(items)}
        for comparator in ("TSCB", "ITPS"):
            col = {"+": 0, "*": 0, "-": 0}
            for item in items:
                a = [int(r["best_cost"]) for r in data[(item["instance"], "NILS")]]
                b = [int(r["best_cost"]) for r in data[(item["instance"], comparator)]]
                outcome, _, _ = significance(a, b)
                col[outcome] += 1
            for sign in ("+", "*", "-"):
                row[f"NILS/{comparator} {sign}"] = col[sign]
        table3_rows.append(row)
    total = {"Graph type": "Total", "Num.": len(manifest)}
    for key in ("NILS/TSCB +", "NILS/TSCB *", "NILS/TSCB -", "NILS/ITPS +", "NILS/ITPS *", "NILS/ITPS -"):
        total[key] = sum(int(r[key]) for r in table3_rows)
    table3_rows.append(total)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "reproduced_table2.csv", table2_rows)
    write_csv(output_dir / "reproduced_table3.csv", table3_rows)
    write_csv(output_dir / "per_instance_metrics.csv", [
        {"instance": item["instance"], "family": item["family"], "algorithm": algo,
         "best_of_50": metrics[(item["instance"], algo)]["best_cost"],
         "avg_cost": metrics[(item["instance"], algo)]["avg_cost"],
         "avg_time_to_best": metrics[(item["instance"], algo)]["avg_time"],
         "rmse": metrics[(item["instance"], algo)]["rmse"],
         "best_target": item["best_target"], "error_target": item["error_target"]}
        for item in manifest for algo in ALGORITHM_ORDER
    ])
    write_table2_tex(output_dir / "reproduced_table2.tex", table2_rows)
    write_table3_tex(output_dir / "reproduced_table3.tex", table3_rows)
    compare_to_published(output_dir, table2_rows, table3_rows)
    print(f"Recreated tables from {len(expected)} successful runs in {output_dir}")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def compare_to_published(
    output_dir: Path,
    table2_rows: list[dict[str, object]],
    table3_rows: list[dict[str, object]],
) -> None:
    """Write a row-by-row check against the committed published reference CSVs."""
    comparisons: list[dict[str, object]] = []
    reference_dir = ROOT / "results/tables/reference"

    with (reference_dir / "published_table2.csv").open(newline="", encoding="utf-8") as handle:
        table2_reference = {r["Graph type"]: r for r in csv.DictReader(handle)}
    table2_fields = [
        "Num.",
        *(f"{algorithm} {metric}" for algorithm in ALGORITHM_ORDER
          for metric in ("Avg. Cbb", "Avg. Tb", "O-RMSE", "% Best")),
    ]
    for row in table2_rows:
        name = str(row["Graph type"])
        reference = table2_reference.get(name)
        if reference is None:
            raise ValueError(f"Published Table 2 reference is missing row {name!r}")
        for field in table2_fields:
            published = reference.get(field, "")
            reproduced = str(row.get(field, ""))
            if not published:
                continue
            if field == "Num." and name != "Win/Match/Fail":
                matches = int(float(published)) == int(float(reproduced))
                delta: object = int(float(reproduced)) - int(float(published))
            elif name == "Win/Match/Fail":
                matches = published == reproduced
                delta = ""
            else:
                published_num, reproduced_num = float(published), float(reproduced)
                matches = round(reproduced_num + 1e-10, 2) == round(published_num, 2)
                delta = reproduced_num - published_num
            comparisons.append({
                "table": "Table 2", "graph_type": name, "metric": field,
                "published": published, "reproduced": reproduced,
                "delta": delta, "matches_published_rounding": int(matches),
            })

    with (reference_dir / "published_table3.csv").open(newline="", encoding="utf-8") as handle:
        table3_reference = {r["Graph type"]: r for r in csv.DictReader(handle)}
    table3_fields = [
        "Num.", "NILS/TSCB +", "NILS/TSCB *", "NILS/TSCB -",
        "NILS/ITPS +", "NILS/ITPS *", "NILS/ITPS -",
    ]
    for row in table3_rows:
        name = str(row["Graph type"])
        reference = table3_reference.get(name)
        if reference is None:
            raise ValueError(f"Published Table 3 reference is missing row {name!r}")
        for field in table3_fields:
            reference_field = field.replace(" -", " −") if field.endswith(" -") else field
            published = reference.get(reference_field, "")
            reproduced = str(row.get(field, ""))
            if not published:
                continue
            matches = int(float(published)) == int(float(reproduced))
            comparisons.append({
                "table": "Table 3", "graph_type": name, "metric": field,
                "published": published, "reproduced": reproduced,
                "delta": int(float(reproduced)) - int(float(published)),
                "matches_published_rounding": int(matches),
            })
    write_csv(output_dir / "published_comparison.csv", comparisons)


def write_table2_tex(path: Path, rows: list[dict[str, object]]) -> None:
    lines = [
        "% Recomputed from raw 50-run benchmark results by scripts/run_published_tables.py.",
        r"\begin{table*}[t]", r"\centering",
        r"\caption{Recomputed performance comparison on the 113 CBP benchmark instances}",
        r"\label{tab:reproduced_table2}", r"\resizebox{\textwidth}{!}{%",
        r"\begin{tabular}{lr|rrrr|rrrr|rrrr}", r"\toprule",
        r" & & \multicolumn{4}{c|}{TSCB} & \multicolumn{4}{c|}{ITPS} & \multicolumn{4}{c}{NILS} " + r"\\",
        r"Graph type & Num. & Avg. $C_{bb}$ & Avg. $T_b$ & O-RMSE & \% Best & Avg. $C_{bb}$ & Avg. $T_b$ & O-RMSE & \% Best & Avg. $C_{bb}$ & Avg. $T_b$ & O-RMSE & \% Best " + r"\\",
        r"\midrule",
    ]
    for row in rows[:-1]:
        cells = [str(row["Graph type"]), str(row["Num."])]
        for algorithm in ALGORITHM_ORDER:
            cells.extend(f"{float(row[f'{algorithm} {key}']):.2f}" for key in ("Avg. Cbb", "Avg. Tb", "O-RMSE", "% Best"))
        lines.append(" & ".join(cells) + r" \\")
    win = str(rows[-1]["Num."])
    lines.extend([r"\midrule", rf"\multicolumn{{2}}{{l}}{{Win/Match/Fail (NILS vs TSCB) = {win}}} & \multicolumn{{12}}{{c}}{{}} " + r"\\", r"\bottomrule", r"\end{tabular}%", "}", r"\end{table*}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_table3_tex(path: Path, rows: list[dict[str, object]]) -> None:
    lines = [
        "% Recomputed from per-run outcomes using the published significance procedure.",
        r"\begin{table}[t]", r"\centering",
        r"\caption{Recomputed statistical comparison on the 113 CBP benchmark instances}",
        r"\label{tab:reproduced_table3}", r"\begin{tabular}{lr|rrr|rrr}", r"\toprule",
        r" & & \multicolumn{3}{c|}{NILS / TSCB} & \multicolumn{3}{c}{NILS / ITPS} " + r"\\",
        r"Graph type & Num. & + & * & $-$ & + & * & $-$ " + r"\\", r"\midrule",
    ]
    for row in rows:
        cells = [str(row["Graph type"]), str(row["Num."])]
        cells.extend(str(row[key]) for key in ("NILS/TSCB +", "NILS/TSCB *", "NILS/TSCB -", "NILS/ITPS +", "NILS/ITPS *", "NILS/ITPS -"))
        lines.append(" & ".join(cells) + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--instances-dir", help="Directory containing all 113 extracted .rnd files")
    parser.add_argument("--raw-csv", default=str(DEFAULT_RAW), help="Resumable raw run log")
    parser.add_argument("--output-dir", default=str(ROOT / "results/tables/reproduced"))
    parser.add_argument("--nils-bin")
    parser.add_argument("--itps-bin")
    parser.add_argument("--algorithms", nargs="+", choices=ALGORITHM_ORDER, default=ALGORITHM_ORDER)
    parser.add_argument("--reps", type=int, default=50)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--time-limit", type=int, default=600)
    parser.add_argument("--timeout-grace", type=int, default=120)
    parser.add_argument("--family", action="append", choices=FAMILY_ORDER, help="Run selected family only; partial runs never produce final tables")
    parser.add_argument("--limit", type=int, help="Run only the first N manifest rows; partial runs never produce final tables")
    parser.add_argument("--tscb-command", help="TSCB command template; placeholders: {instance}, {name}, {seed}, {rep}, {lower_bound}, {time_limit}")
    parser.add_argument("--tscb-cost-regex", help="Regex on TSCB output; first capture group must be best cost")
    parser.add_argument("--tscb-time-regex", help="Regex on TSCB output; first capture group must be time-to-best in seconds")
    parser.add_argument("--aggregate-only", action="store_true", help="Regenerate tables from an existing complete raw CSV")
    parser.add_argument("--overwrite", action="store_true", help="Re-run records already present in the raw CSV")
    args = parser.parse_args()
    if args.reps <= 0 or args.time_limit <= 0:
        parser.error("--reps and --time-limit must be positive")
    if args.timeout_grace < 0 or (args.limit is not None and args.limit <= 0):
        parser.error("--timeout-grace must be non-negative and --limit must be positive")
    if len(set(args.algorithms)) != len(args.algorithms):
        parser.error("--algorithms cannot contain duplicates")
    return args


def main() -> int:
    args = parse_args()
    try:
        manifest = load_manifest(Path(args.manifest))
        if args.aggregate_only:
            aggregate(Path(args.raw_csv), manifest, Path(args.output_dir))
        else:
            run_suite(manifest, args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
