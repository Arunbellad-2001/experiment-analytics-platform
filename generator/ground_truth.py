"""Step 12: Separate Ground-Truth CSV and JSON file generator (strictly external to SQLite)."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional, Tuple

from config.settings import GROUND_TRUTH_DIR
from generator.anomaly_generator import InjectedAnomalySpec


def write_ground_truth_files(
    specs: List[InjectedAnomalySpec],
    output_dir: Optional[Path] = None,
) -> Tuple[Path, Path]:
    """Write ground-truth scenario labels exclusively to external CSV and JSON files."""
    target_dir = Path(output_dir) if output_dir is not None else GROUND_TRUTH_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    sorted_specs = sorted(specs, key=lambda s: s.scenario_id)
    rows = [asdict(s) for s in sorted_specs]

    csv_path = target_dir / "ground_truth.csv"
    json_path = target_dir / "ground_truth.json"

    fieldnames = [
        "scenario_id",
        "experiment_id",
        "affected_entity",
        "affected_record_id",
        "expected_anomaly_type",
        "expected_detection_result",
        "expected_decision",
        "generation_rule",
    ]

    with csv_path.open("w", encoding="utf-8", newline="\n") as f_csv:
        writer = csv.DictWriter(f_csv, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    with json_path.open("w", encoding="utf-8", newline="\n") as f_json:
        json.dump({"ground_truth_scenarios": rows}, f_json, indent=2, sort_keys=True)
        f_json.write("\n")

    return csv_path, json_path