"""Plot generation for experiment records using CNSPlots."""
from __future__ import annotations

from pathlib import Path


MEASURED_STATUSES = {"OPTIMAL", "TIMEOUT", "FEASIBLE"}


def _pyplot():
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    return plt


def _plotting():
    try:
        import cnsplots as cns
        import matplotlib.pyplot as plt
        import pandas as pd
    except ImportError as error:
        raise RuntimeError(
            "Plot generation requires the project dependencies, including cnsplots."
        ) from error
    return cns, plt, pd


def _elapsed_seconds(row: dict) -> float | None:
    """Return total wall time while respecting timeout-record semantics."""
    solve_time = row.get("solve_time")
    if solve_time is None or row.get("status") not in MEASURED_STATUSES:
        return None

    # Incremental SAT runs report elapsed process time as solve_time on timeout;
    # external solver wrappers keep encoding_time and solve_time separate.
    incremental_run = row.get("group") != "methods" or row.get("method") == "SAT"
    if row.get("status") == "TIMEOUT" and incremental_run:
        return max(float(solve_time), 1e-3)
    return max(float(row.get("encoding_time") or 0.0) + float(solve_time), 1e-3)


def _save(cns, plt, figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cns.savefig(path, fig=figure, dpi=180)
    plt.close(figure)


def _plot_grouped_runtimes(
    rows: list[dict],
    directory: Path,
    filename: str,
    hue_key: str,
    hue_order: list[str],
    title: str,
) -> None:
    cns, plt, pd = _plotting()
    instances = sorted({row["instance"] for row in rows})
    if not instances or not hue_order:
        return

    lookup: dict[tuple[str, str], dict] = {}
    observations = []
    excluded = 0
    timeout_count = 0
    for row in rows:
        category = row.get(hue_key)
        if category is None:
            continue
        lookup[(row["instance"], category)] = row
        seconds = _elapsed_seconds(row)
        if seconds is None:
            excluded += 1
            continue
        if row.get("status") == "TIMEOUT":
            timeout_count += 1
        observations.append({
            "instance": row["instance"],
            "runtime": seconds,
            hue_key: category,
        })

    if not observations:
        return

    figure = cns.figure(
        width=max(800, 36 * len(instances) + 200),
        height=330,
        unit="pt",
        color_cycle="Set2",
    )
    axis = figure.subplots()
    cns.barplot(
        data=pd.DataFrame(observations),
        x="instance",
        y="runtime",
        hue=hue_key,
        order=instances,
        hue_order=hue_order,
        errorbar=None,
        palette="Set2",
        ax=axis,
    )
    axis.set_yscale("log")
    axis.set(title=title, xlabel="instance", ylabel="wall time (s)")
    axis.tick_params(axis="x", labelrotation=65)

    # Timeout runs remain visible and are distinguished from completed runs.
    for hue_index, container in enumerate(axis.containers[:len(hue_order)]):
        category = hue_order[hue_index]
        for instance_index, patch in enumerate(container.patches):
            if instance_index >= len(instances):
                break
            record = lookup.get((instances[instance_index], category))
            if record and record.get("status") == "TIMEOUT":
                patch.set_hatch("//")

    axis.text(
        0.0,
        -0.42,
        f"Hatched bars: timeout ({timeout_count}); runs without measured time "
        f"excluded: {excluded}.",
        transform=axis.transAxes,
        fontsize=8,
        va="top",
    )
    figure.tight_layout()
    _save(cns, plt, figure, directory / filename)


def plot_methods(rows: list[dict], directory: Path) -> None:
    preferred = ("SAT", "CP-SAT", "CPLEX CP", "CPLEX MIP", "Gurobi")
    present = {row.get("method") for row in rows}
    methods = [method for method in preferred if method in present]
    methods.extend(sorted(method for method in present if method and method not in methods))
    _plot_grouped_runtimes(
        rows, directory, "method_times.png", "method", methods, "Solver runtime by instance"
    )


def plot_encoding(rows: list[dict], directory: Path) -> None:
    configured = []
    for row in rows:
        item = dict(row)
        item["configuration"] = (
            f"{row.get('distance', 'unknown')} + {row.get('exactly_one', 'unknown')}"
        )
        configured.append(item)
    configurations = sorted({row["configuration"] for row in configured})
    _plot_grouped_runtimes(
        configured,
        directory,
        "encoding_configs.png",
        "configuration",
        configurations,
        "Encoding runtime by instance",
    )


def plot_incumbents(rows: list[dict], directory: Path) -> None:
    cns, plt, pd = _plotting()
    by_instance: dict[str, list[dict]] = {}
    for row in rows:
        if row.get("incumbents"):
            by_instance.setdefault(row["instance"], []).append(row)
    if not by_instance:
        return

    instances = sorted(by_instance)
    figure = cns.figure(width=max(800, 340 * len(instances)), height=280, unit="pt")
    axes = figure.subplots(1, len(instances), squeeze=False)[0]

    for axis, name in zip(axes, instances):
        observations = []
        for run_index, row in enumerate(by_instance[name]):
            points = row["incumbents"]
            label = row.get("level") or row.get("method") or f"run {run_index + 1}"
            if row.get("distance"):
                label += f" ({row['distance']} + {row.get('exactly_one', 'EO')})"
            for point in points:
                observations.append({
                    "elapsed": max(float(point["elapsed"]), 1e-3),
                    "ub": point["ub"],
                    "run": label,
                })
            end = _elapsed_seconds(row)
            last_elapsed = max(float(point["elapsed"]) for point in points)
            if end is not None and end > last_elapsed:
                observations.append({
                    "elapsed": float(end),
                    "ub": points[-1]["ub"],
                    "run": label,
                })

        if observations:
            cns.lineplot(
                data=pd.DataFrame(observations),
                x="elapsed",
                y="ub",
                hue="run",
                estimator=None,
                errorbar=None,
                drawstyle="steps-post",
                ax=axis,
            )
        axis.set(title=name, xlabel="wall time incl. encoding (s)", ylabel="best UB")
        axis.set_xscale("log")
        axis.legend(fontsize="x-small")

    figure.tight_layout()
    _save(cns, plt, figure, directory / "ub_vs_time.png")


def plot_ablation(rows: list[dict], directory: Path) -> None:
    levels = ("weak", "medium", "strong", "no_rotation", "no_reflection", "no_heuristic")
    _plot_grouped_runtimes(
        rows,
        directory,
        "per_level_times.png",
        "level",
        [level for level in levels if any(row.get("level") == level for row in rows)],
        "Ablation runtime by instance",
    )
