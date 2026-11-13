"""End-to-end 13-step synthetic data generation orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from config.settings import (
    FULL_CONFIG,
    GROUND_TRUTH_DIR,
    STARTER_CONFIG,
    DatasetScaleConfig,
)
from database.connection import init_db, session_scope
from generator.anomaly_generator import inject_labelled_anomalies
from generator.assignment_generator import generate_assignments_for_all_experiments
from generator.audience_generator import generate_audience_members
from generator.event_generator import simulate_exposures_and_conversions
from generator.ground_truth import write_ground_truth_files
from generator.master_data import generate_master_data
from services.anomaly_detection import detect_all_anomalies
from services.experiment_service import transition_experiment_status
from services.ground_truth_evaluator import evaluate_detections_against_ground_truth
from services.statistics import run_experiment_analysis
from services.validation import run_all_validation_checks


@dataclass(frozen=True)
class PipelineExecutionSummary:
    """Summary returned after running the 13-step generation and evaluation pipeline."""

    mode_name: str
    random_seed: int
    entity_counts: Dict[str, int]
    validation_summary: Dict[str, Any]
    ground_truth_summary: Dict[str, Any]
    ground_truth_csv_path: Path
    ground_truth_json_path: Path


def reset_operational_tables(engine: Engine) -> None:
    """Drop and recreate operational tables cleanly from database/schema.sql."""
    raw_conn = engine.raw_connection()
    try:
        cursor = raw_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = OFF;")
        tables = [
            "experiment_issues",
            "experiment_events",
            "experiment_results",
            "guardrail_metrics",
            "metric_definitions",
            "conversion_events",
            "exposure_events",
            "assignments",
            "audience_members",
            "variants",
            "experiments",
        ]
        for tbl in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {tbl};")
        raw_conn.commit()
    finally:
        raw_conn.close()
    init_db(engine=engine)


def run_generation_pipeline(
    engine: Engine,
    config: DatasetScaleConfig = STARTER_CONFIG,
    inject_anomalies: bool = True,
    ground_truth_dir: Optional[Path] = None,
) -> PipelineExecutionSummary:
    """Execute Steps 1 through 13 in strict sequence with deterministic seed control."""
    reset_operational_tables(engine)
    target_gt_dir = (
        Path(ground_truth_dir) if ground_truth_dir is not None else GROUND_TRUTH_DIR
    )

    with session_scope(engine) as session:
        # Steps 1, 2, 8 & 9: Experiments, Variants, MetricDefinitions (V1), and GuardrailMetrics
        experiments, _, _, _ = generate_master_data(session, config)

        # Steps 3 & 4: AudienceMembers and Eligibility Filtering
        pools = generate_audience_members(session, config)

        # Step 5: Randomized Assignments (with SRM skew on EXP-2026-000005 if inject_anomalies=True)
        assignments_by_exp = generate_assignments_for_all_experiments(
            session,
            config=config,
            experiment_user_pools=pools,
            inject_srm_on_designated=inject_anomalies,
        )

        # Steps 6 & 7: ExposureEvents and ConversionEvents
        simulate_exposures_and_conversions(session, config, assignments_by_exp)

        # Step 10: Calculate initial ExperimentResults from source records
        for exp in experiments:
            run_experiment_analysis(
                session,
                experiment_id=exp.experiment_id,
                analysis_run_id=f"RUN-{exp.experiment_id}-001",
                analysis_timestamp="2026-01-20T00:00:00Z",
                analysis_methods=("ITT", "EXPOSED_SECONDARY"),
            )
            transition_experiment_status(
                session,
                experiment_id=exp.experiment_id,
                target_status="Completed",
                actor="Data_Analyst",
                event_timestamp="2026-01-21T00:00:00Z",
                notes="Completed initial experiment window and recorded Run 001 analysis",
            )

        # Step 11: Inject labelled negative edge cases
        injected_specs = (
            inject_labelled_anomalies(session, config) if inject_anomalies else []
        )

        # Step 12: Write external ground-truth CSV and JSON files
        gt_csv_path, gt_json_path = write_ground_truth_files(
            injected_specs, output_dir=target_gt_dir
        )

        # Step 13: Run blind anomaly detection and full QA validation checks
        detect_all_anomalies(session, detected_at="2026-01-26T00:00:00Z")

        # Re-run analysis on EXP-2026-000005 so its post-anomaly ExperimentResult reflects INVALID_DATA_HOLD
        if inject_anomalies:
            run_experiment_analysis(
                session,
                experiment_id="EXP-2026-000005",
                analysis_run_id="RUN-EXP-2026-000005-002",
                analysis_timestamp="2026-01-27T00:00:00Z",
                analysis_methods=("ITT", "EXPOSED_SECONDARY"),
            )

        val_summary = run_all_validation_checks(session)
        gt_eval = evaluate_detections_against_ground_truth(
            session, ground_truth_json_path=gt_json_path
        )

        return PipelineExecutionSummary(
            mode_name=config.mode_name,
            random_seed=config.random_seed,
            entity_counts=val_summary["entity_counts"],
            validation_summary=val_summary,
            ground_truth_summary={
                "total_expected_anomalies": gt_eval.total_expected_anomalies,
                "total_detected_anomalies": gt_eval.total_detected_anomalies,
                "true_positives": gt_eval.true_positives,
                "false_positives": gt_eval.false_positives,
                "false_negatives": gt_eval.false_negatives,
                "precision": gt_eval.precision,
                "recall": gt_eval.recall,
                "detection_coverage": gt_eval.detection_coverage,
            },
            ground_truth_csv_path=gt_csv_path,
            ground_truth_json_path=gt_json_path,
        )