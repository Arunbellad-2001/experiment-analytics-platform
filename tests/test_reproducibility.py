"""Automated test suite for Milestones 5 & 6: Anomaly detection, Ground-truth isolation, and SHA-256 Reproducibility."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from config.settings import STARTER_CONFIG
from database.connection import init_db, session_scope
from exports.export_data import export_all_datasets
from generator.pipeline import run_generation_pipeline
from services.anomaly_detection import detect_all_anomalies
from services.ground_truth_evaluator import evaluate_detections_against_ground_truth


def test_end_to_end_reproducibility_and_sha256_checksums(tmp_path: Path) -> None:
    """Run the 13-step generator twice with the same seed and verify 100% identical SHA-256 checksums."""
    db_path_1 = tmp_path / "run1.db"
    db_path_2 = tmp_path / "run2.db"
    gt_dir_1 = tmp_path / "gt1"
    gt_dir_2 = tmp_path / "gt2"
    exp_dir_1 = tmp_path / "exports1"
    exp_dir_2 = tmp_path / "exports2"

    engine1 = init_db(db_path=db_path_1)
    engine2 = init_db(db_path=db_path_2)

    try:
        sum1 = run_generation_pipeline(
            engine1, config=STARTER_CONFIG, inject_anomalies=True, ground_truth_dir=gt_dir_1
        )
        sum2 = run_generation_pipeline(
            engine2, config=STARTER_CONFIG, inject_anomalies=True, ground_truth_dir=gt_dir_2
        )

        assert sum1.entity_counts == sum2.entity_counts
        assert sum1.validation_summary["overall_passed"] is True
        assert sum1.ground_truth_summary["true_positives"] == 5
        assert sum1.ground_truth_summary["false_positives"] == 0
        assert sum1.ground_truth_summary["false_negatives"] == 0
        assert sum1.ground_truth_summary["precision"] == 1.0
        assert sum1.ground_truth_summary["recall"] == 1.0
        assert sum1.ground_truth_summary["detection_coverage"] == 1.0

        with session_scope(engine1) as s1, session_scope(engine2) as s2:
            payload1 = export_all_datasets(
                s1, output_dir=exp_dir_1, ground_truth_dir=gt_dir_1
            )
            payload2 = export_all_datasets(
                s2, output_dir=exp_dir_2, ground_truth_dir=gt_dir_2
            )

        checksums_1 = {
            m["file_name"]: m["sha256_checksum"] for m in payload1["manifest"]
        }
        checksums_2 = {
            m["file_name"]: m["sha256_checksum"] for m in payload2["manifest"]
        }
        assert len(checksums_1) >= 23
        assert checksums_1 == checksums_2
    finally:
        engine1.dispose()
        engine2.dispose()


def test_ground_truth_complete_isolation(tmp_path: Path) -> None:
    """Verify anomaly detection works without ground-truth files and ground-truth evaluation performs zero DB writes."""
    db_path = tmp_path / "isolation.db"
    gt_dir = tmp_path / "gt_isolated"
    engine = init_db(db_path=db_path)

    try:
        run_generation_pipeline(
            engine, config=STARTER_CONFIG, inject_anomalies=True, ground_truth_dir=gt_dir
        )

        with session_scope(engine) as session:
            # Verify ground-truth evaluation performs zero database writes
            before_changes = session.execute(text("SELECT total_changes()")).scalar_one()
            gt_eval = evaluate_detections_against_ground_truth(
                session, ground_truth_json_path=gt_dir / "ground_truth.json"
            )
            after_changes = session.execute(text("SELECT total_changes()")).scalar_one()
            assert before_changes == after_changes
            assert gt_eval.true_positives == 5

            # Delete external ground-truth files and verify blind anomaly detection still runs identically
            (gt_dir / "ground_truth.json").unlink()
            (gt_dir / "ground_truth.csv").unlink()
            issues = detect_all_anomalies(session)
            assert len(issues) == 5
    finally:
        engine.dispose()