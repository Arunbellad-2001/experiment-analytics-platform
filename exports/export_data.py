"""Section 15: Canonical CSV, JSON, SQL seed, and SHA-256 source manifest export engine."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from config.settings import (
    DEFAULT_RANDOM_SEED,
    GENERATOR_VERSION,
    GROUND_TRUTH_DIR,
    REFERENCE_EPOCH_ISO,
)
from services.ground_truth_evaluator import evaluate_detections_against_ground_truth
from services.validation import run_all_validation_checks


@dataclass(frozen=True)
class ExportedFileManifestEntry:
    """Metadata and SHA-256 checksum for a single exported dataset artifact."""

    dataset_name: str
    file_name: str
    export_format: str
    row_count: int
    sha256_checksum: str
    generation_method: str
    random_seed: int
    generator_version: str
    generation_timestamp: str
    data_provenance: str


ENTITY_EXPORT_SPECS: Tuple[Tuple[str, str, str], ...] = (
    ("experiments", "experiments.csv", "experiment_id"),
    ("variants", "variants.csv", "variant_id"),
    ("audience_members", "audience_members.csv", "user_id"),
    ("assignments", "assignments.csv", "assignment_id"),
    ("exposure_events", "exposure_events.csv", "exposure_id"),
    ("conversion_events", "conversion_events.csv", "conversion_id"),
    ("metric_definitions", "metric_definitions.csv", "metric_id"),
    ("guardrail_metrics", "guardrail_metrics.csv", "guardrail_id"),
    ("experiment_results", "experiment_results.csv", "result_id"),
    ("experiment_events", "experiment_events.csv", "event_id"),
    ("experiment_issues", "experiment_issues.csv", "issue_id"),
)


def compute_file_sha256(file_path: Path) -> str:
    """Compute canonical hex SHA-256 checksum of a file."""
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _format_canonical_value(val: Any) -> Any:
    """Format floating-point numbers and nulls canonically for deterministic serialization."""
    if val is None:
        return ""
    if isinstance(val, float):
        return f"{val:.8f}"
    return val


def export_all_datasets(
    session: Session,
    output_dir: Path,
    ground_truth_dir: Optional[Path] = None,
    random_seed: int = DEFAULT_RANDOM_SEED,
    generation_timestamp: str = REFERENCE_EPOCH_ISO,
) -> Dict[str, Any]:
    """Export all entities to canonical CSV, JSON, SQL seed script, validation_summary.json, and manifest."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    gt_dir = Path(ground_truth_dir) if ground_truth_dir is not None else GROUND_TRUTH_DIR

    manifest_entries: List[ExportedFileManifestEntry] = []
    sql_seed_lines: List[str] = [
        "-- Canonical SQL Seed Dump for Experiment Analytics Platform",
        "PRAGMA foreign_keys = ON;",
        "BEGIN TRANSACTION;",
    ]

    for table_name, csv_filename, pk_col in ENTITY_EXPORT_SPECS:
        pragma_rows = session.execute(
            text(f"PRAGMA table_info({table_name})")
        ).fetchall()
        columns: List[str] = [str(r[1]) for r in pragma_rows]

        query = text(f"SELECT {', '.join(columns)} FROM {table_name} ORDER BY {pk_col} ASC")
        rows = session.execute(query).fetchall()

        # 1. Write Canonical CSV
        csv_path = output_dir / csv_filename
        with csv_path.open("w", encoding="utf-8", newline="\n") as f_csv:
            writer = csv.writer(f_csv, lineterminator="\n")
            writer.writerow(columns)
            for row in rows:
                writer.writerow([_format_canonical_value(v) for v in row])

        manifest_entries.append(
            ExportedFileManifestEntry(
                dataset_name=table_name,
                file_name=csv_filename,
                export_format="CSV",
                row_count=len(rows),
                sha256_checksum=compute_file_sha256(csv_path),
                generation_method="Parameterized 13-Step Deterministic Pipeline",
                random_seed=random_seed,
                generator_version=GENERATOR_VERSION,
                generation_timestamp=generation_timestamp,
                data_provenance="100% Synthetic Controlled PRNG (PCG64)",
            )
        )

        # 2. Write Canonical JSON
        json_filename = csv_filename.replace(".csv", ".json")
        json_path = output_dir / json_filename
        dict_rows = [
            {
                col: (round(val, 8) if isinstance(val, float) else val)
                for col, val in zip(columns, row)
            }
            for row in rows
        ]
        with json_path.open("w", encoding="utf-8", newline="\n") as f_json:
            json.dump({table_name: dict_rows}, f_json, indent=2, sort_keys=True)
            f_json.write("\n")

        manifest_entries.append(
            ExportedFileManifestEntry(
                dataset_name=f"{table_name}_json",
                file_name=json_filename,
                export_format="JSON",
                row_count=len(rows),
                sha256_checksum=compute_file_sha256(json_path),
                generation_method="Parameterized 13-Step Deterministic Pipeline",
                random_seed=random_seed,
                generator_version=GENERATOR_VERSION,
                generation_timestamp=generation_timestamp,
                data_provenance="100% Synthetic Controlled PRNG (PCG64)",
            )
        )

        # 3. Append INSERT statements to SQL seed dump
        for row in rows:
            formatted_vals: List[str] = []
            for v in row:
                if v is None:
                    formatted_vals.append("NULL")
                elif isinstance(v, (int, float)):
                    formatted_vals.append(
                        f"{v:.8f}" if isinstance(v, float) else str(v)
                    )
                else:
                    escaped = str(v).replace("'", "''")
                    formatted_vals.append(f"'{escaped}'")
            cols_sql = ", ".join(columns)
            vals_sql = ", ".join(formatted_vals)
            sql_seed_lines.append(
                f"INSERT INTO {table_name} ({cols_sql}) VALUES ({vals_sql});"
            )

    sql_seed_lines.append("COMMIT;")
    sql_seed_path = output_dir / "seed_data.sql"
    sql_seed_path.write_text("\n".join(sql_seed_lines) + "\n", encoding="utf-8")

    # Copy/include ground_truth.csv and ground_truth.json in output_dir if present
    gt_csv_src = gt_dir / "ground_truth.csv"
    gt_json_src = gt_dir / "ground_truth.json"
    if gt_csv_src.exists():
        gt_csv_dst = output_dir / "ground_truth.csv"
        if gt_csv_src.resolve() != gt_csv_dst.resolve():
            gt_csv_dst.write_bytes(gt_csv_src.read_bytes())
        gt_row_cnt = max(0, len(gt_csv_dst.read_text(encoding="utf-8").splitlines()) - 1)
        manifest_entries.append(
            ExportedFileManifestEntry(
                dataset_name="ground_truth",
                file_name="ground_truth.csv",
                export_format="CSV",
                row_count=gt_row_cnt,
                sha256_checksum=compute_file_sha256(gt_csv_dst),
                generation_method="Isolated Anomaly Ground-Truth Generator",
                random_seed=random_seed,
                generator_version=GENERATOR_VERSION,
                generation_timestamp=generation_timestamp,
                data_provenance="100% Synthetic Assessment Scenarios",
            )
        )

    # Generate validation_summary.json combining QA validation + Ground-Truth evaluation
    val_summary = run_all_validation_checks(session)
    gt_summary_dict: Dict[str, Any] = {}
    if gt_json_src.exists():
        gt_eval = evaluate_detections_against_ground_truth(
            session, ground_truth_json_path=gt_json_src
        )
        gt_summary_dict = asdict(gt_eval)

    validation_payload = {
        "random_seed": random_seed,
        "generator_version": GENERATOR_VERSION,
        "generation_timestamp": generation_timestamp,
        "validation_checks": val_summary,
        "ground_truth_evaluation": gt_summary_dict,
        "manifest": [asdict(m) for m in manifest_entries],
    }
    val_json_path = output_dir / "validation_summary.json"
    with val_json_path.open("w", encoding="utf-8", newline="\n") as f_val:
        json.dump(validation_payload, f_val, indent=2, sort_keys=True)
        f_val.write("\n")

    return validation_payload