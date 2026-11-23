"""Small helpers for names, files, and result records."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path


def canonical(name: str) -> str:
    return name.removesuffix(".mtx").replace("_", "")


def display_name(name: str) -> str:
    return re.sub(r"_+", "_", name.removesuffix(".mtx"))


def find_instance_path(datasets: Path, name: str) -> Path:
    target = canonical(name)
    for path in datasets.glob("*.mtx"):
        if canonical(path.stem) == target:
            return path
    raise FileNotFoundError(f"no MatrixMarket file for {name!r} in {datasets}")


def read_lower_bounds(path: Path) -> dict[str, int]:
    with path.open(newline="") as stream:
        return {canonical(row["instance"]): int(row["lb"]) for row in csv.DictReader(stream)}


def completed_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {json.loads(line)["key"] for line in path.read_text().splitlines()
            if line.strip() and json.loads(line)["status"] != "UNAVAILABLE" and json.loads(line)["status"] != "ERROR"}


def write_record(path: Path, record: dict) -> None:
    records = [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()
               if line.strip()] if path.exists() else []
    records = [row for row in records if row["key"] != record["key"]]
    records.append(record)
    with path.open("w", encoding="utf8") as stream:
        for row in records:
            stream.write(json.dumps(row, default=str) + "\n")


def export_csv(records_path: Path, output: Path) -> list[dict]:
    rows = [json.loads(line) for line in records_path.read_text().splitlines() if line.strip()]
    fieldnames = sorted({key for row in rows for key in row if key not in {"incumbents", "key"}})
    with output.open("w", newline="", encoding="utf8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: value for key, value in row.items() if key in fieldnames} for row in rows)
    return rows
