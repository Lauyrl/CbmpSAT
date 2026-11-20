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

    configs = sorted({(r["distance"], r["exactly_one"]) for r in rows})
    instances = sorted({r["instance"] for r in rows})
    width = 0.8 / len(configs)

    figure, axis = plt.subplots()
    for k, (distance, eo) in enumerate(configs):
        label = f"{distance}+{eo}"
        for i, name in enumerate(instances):
            same_config = [r for r in rows if r["instance"] == name
                           and r["distance"] == distance and r["exactly_one"] == eo]
            match = [r for r in same_config
                     if r["status"] != "ENCODING_FAILED" and r["solve_time"] is not None]
            failed = [r for r in same_config if r["status"] == "ENCODING_FAILED"]
            x = i + k * width

            if match:
                axis.bar(x, match[0]["solve_time"], width, label=label, color=f"C{k}",
                         hatch="//" if match[0]["status"] == "TIMEOUT" else None)
                label = None  # one legend entry per config
            elif failed:
                axis.text(x, 0, "✗", color="red", ha="center", va="bottom", fontsize=12)

    axis.set_xticks([i + 0.4 - width / 2 for i in range(len(instances))], instances)
    axis.set(ylabel="solve time (s)")
    axis.legend()
    figure.tight_layout()
    figure.savefig(directory / "encoding_configs.png", dpi=180)
    plt.close(figure)


def plot_incumbents(rows: list[dict], directory: Path) -> None:
    plt = _pyplot()
    if plt is None:
        return

    by_instance: dict[str, list[dict]] = {}
    for row in rows:
        if row.get("incumbents"):
            by_instance.setdefault(row["instance"], []).append(row)

    if not by_instance:
        return

    figure, axes = plt.subplots(1, len(by_instance), figsize=(4 * len(by_instance), 3), squeeze=False)
    for axis, (name, group) in zip(axes[0], by_instance.items()):
        for row in group:
            points = row["incumbents"]
            end = row["timeout_seconds"] if row["status"] == "TIMEOUT" else (row.get("encoding_time") or 0) + row["solve_time"]
            label = f"{row['method']} {row.get('key', '')[-40:]}" if len(group) > 1 else row["method"]
            axis.step([max(p["elapsed"], 1e-3) for p in points] + [end],
                      [p["ub"] for p in points] + [points[-1]["ub"]],
                      where="post", label=label)
        axis.set(title=name, xlabel="elapsed incl. encoding (s)", ylabel="best UB", xscale="log")
        axis.legend(fontsize="x-small")

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
        times, hatches = [], []
        for level in levels:
            row = values.get(level)
            if row is None:
                times.append(0); hatches.append("")
                axis.text(levels.index(level), 1, "n/a", ha="center")
            elif row["status"] == "OPTIMAL":
                times.append((row["encoding_time"] or 0) + row["solve_time"]); hatches.append("")
            else:
                times.append(row["solve_time"] or 0); hatches.append("//")  # TIMEOUT/ERROR: total elapsed already
        bars = axis.bar(levels, times)
        for bar, hatch in zip(bars, hatches):
            bar.set_hatch(hatch)
        axis.set_yscale("log")
        axis.set(title=name, ylabel="time (s)")

    figure.tight_layout()
    figure.savefig(directory / "per_level_times.png", dpi=180)
    plt.close(figure)
