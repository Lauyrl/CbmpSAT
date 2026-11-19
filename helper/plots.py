"""Plot generation for completed experiment records."""
from __future__ import annotations

from pathlib import Path


def _pyplot():
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    return plt


def plot_methods(rows: list[dict], directory: Path) -> None:
    plt = _pyplot()
    if plt is None:
        return

    timed = [row for row in rows if row["encoding_time"] is not None]
    labels = [f"{row['instance']}\n{row['method']}" for row in timed]
    times = [row["encoding_time"] + row["solve_time"] for row in timed]

    figure, axis = plt.subplots(figsize=(max(6, len(labels) * 0.65), 4))
    axis.bar(range(len(times)), times)
    axis.set(xticks=range(len(times)), xticklabels=labels, ylabel="time (s)")
    axis.tick_params(axis="x", labelrotation=70)
    figure.tight_layout()
    figure.savefig(directory / "method_times.png", dpi=180)
    plt.close(figure)


def plot_encoding(rows: list[dict], directory: Path) -> None:
    plt = _pyplot()
    if plt is None:
        return

    figure, axis = plt.subplots()
    for method, style in (("direct", "o-"), ("order", "s-")):
        points = sorted((row["n"], row["clauses"] / row["edges"]) for row in rows
                        if row["method"] == method and row["exactly_one"] == "product"
                        and row["status"] != "ENCODING_FAILED"
                        and row["clauses"] is not None and row["edges"] > 0)
        if points:
            axis.plot(*zip(*points), style, label=f"{method} measured")

    analytical = sorted((row["n"], row["clauses"] / row["edges"]) for row in rows
                        if row["method"] == "direct" and row["exactly_one"] == "product"
                        and row["status"] == "ENCODING_FAILED"
                        and row["clauses"] is not None and row["edges"] > 0)
    if analytical:
        axis.plot(*zip(*analytical), "k--", label="direct analytical")

    axis.set(xlabel="N", ylabel="clauses per edge", yscale="log")
    axis.legend()
    figure.tight_layout()
    figure.savefig(directory / "clauses_per_edge.png", dpi=180)
    plt.close(figure)

    plot_methods(rows, directory)


def plot_incumbents(rows: list[dict], directory: Path) -> None:
    plt = _pyplot()
    if plt is None:
        return

    figure, axis = plt.subplots()
    for row in rows:
        values = row.get("incumbents", [])
        if values:
            elapsed = [point["elapsed"] for point in values]
            bounds = [point["ub"] for point in values]
            axis.step([0] + elapsed, [bounds[0]] + bounds, where="post", label=f"{row['instance']} / {row['method']}")

    axis.set(xlabel="elapsed time, including encoding (s)", ylabel="best UB")
    axis.legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(directory / "ub_vs_time.png", dpi=180)
    plt.close(figure)


def plot_ablation(rows: list[dict], directory: Path) -> None:
    plt = _pyplot()
    if plt is None:
        return

    levels = ("weak", "medium", "strong")
    instances = sorted({row["instance"] for row in rows})
    figure, axes = plt.subplots(1, len(instances), figsize=(4 * len(instances), 3), squeeze=False)
    for axis, name in zip(axes[0], instances):
        values = {row.get("level"): row for row in rows if row["instance"] == name}
        times = [(values[level]["encoding_time"] or 0) + (values[level]["solve_time"] or 0)
                 if level in values else 0 for level in levels]
        axis.bar(levels, times)
        axis.set(title=name, ylabel="time (s)")

    figure.tight_layout()
    figure.savefig(directory / "per_level_times.png", dpi=180)
    plt.close(figure)
