"""Section 13: Read-only Ground-Truth Evaluation Service (compares detected issues against external ground-truth files)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from config.settings import GROUND_TRUTH_DIR
from database.models import ExperimentIssue
from services.statistics import evaluate_current_launch_decision


@dataclass(frozen=True)
class GroundTruthComparisonRow:
    """Line-item comparison between a Ground-Truth scenario and operational detection."""

    scenario_id: str
    experiment_id: str
    affected_entity: str
    affected_record_id: str
    expected_anomaly_type: str
    detected: bool
    matched_issue_id: Optional[str]
    expected_decision: str
    actual_decision: str
    decision_matched: bool
    generation_rule: str


@dataclass(frozen=True)
class GroundTruthEvaluationSummary:
    """Precision, recall, and coverage metrics comparing detected issues to external ground truth."""

    total_expected_anomalies: int
    total_detected_anomalies: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    detection_coverage: float
    scenario_comparisons: List[GroundTruthComparisonRow]


def evaluate_detections_against_ground_truth(
    session: Session,
    ground_truth_json_path: Optional[Path] = None,
) -> GroundTruthEvaluationSummary:
    """Compare operational experiment_issues against external ground_truth.json in strictly read-only mode."""
    gt_path = (
        Path(ground_truth_json_path)
        if ground_truth_json_path is not None
        else (GROUND_TRUTH_DIR / "ground_truth.json")
    )
    if not gt_path.exists():
        raise FileNotFoundError(f"Ground-truth JSON file not found at: {gt_path}")

    payload = json.loads(gt_path.read_text(encoding="utf-8"))
    gt_rows: List[Dict[str, Any]] = payload.get("ground_truth_scenarios", [])

    detected_issues = list(
        session.scalars(
            select(ExperimentIssue).order_by(ExperimentIssue.issue_id.asc())
        ).all()
    )

    # Key by (experiment_id, issue_type, affected_record_id)
    detected_map: Dict[Tuple[str, str, str], ExperimentIssue] = {
        (iss.experiment_id, iss.issue_type, iss.affected_record_id): iss
        for iss in detected_issues
    }
    expected_keys: Set[Tuple[str, str, str]] = set()
    comparisons: List[GroundTruthComparisonRow] = []

    for row in gt_rows:
        exp_id = str(row["experiment_id"])
        anom_type = str(row["expected_anomaly_type"])
        rec_id = str(row["affected_record_id"])
        key = (exp_id, anom_type, rec_id)
        expected_keys.add(key)

        matched_issue = detected_map.get(key)
        live_decisions = evaluate_current_launch_decision(session, exp_id)
        trt_var_id = f"VAR-{exp_id}-B"
        actual_dec = live_decisions.get(trt_var_id, "UNKNOWN")
        expected_dec = str(row["expected_decision"])

        comparisons.append(
            GroundTruthComparisonRow(
                scenario_id=str(row["scenario_id"]),
                experiment_id=exp_id,
                affected_entity=str(row["affected_entity"]),
                affected_record_id=rec_id,
                expected_anomaly_type=anom_type,
                detected=matched_issue is not None,
                matched_issue_id=matched_issue.issue_id if matched_issue else None,
                expected_decision=expected_dec,
                actual_decision=actual_dec,
                decision_matched=(actual_dec == expected_dec),
                generation_rule=str(row["generation_rule"]),
            )
        )

    detected_keys = set(detected_map.keys())
    tp = len(expected_keys.intersection(detected_keys))
    fp = len(detected_keys - expected_keys)
    fn = len(expected_keys - detected_keys)

    total_expected = len(expected_keys)
    total_detected = len(detected_keys)

    precision = (tp / total_detected) if total_detected > 0 else 1.0
    recall = (tp / total_expected) if total_expected > 0 else 1.0
    coverage = (
        sum(1 for c in comparisons if c.detected and c.decision_matched)
        / total_expected
        if total_expected > 0
        else 1.0
    )

    return GroundTruthEvaluationSummary(
        total_expected_anomalies=total_expected,
        total_detected_anomalies=total_detected,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        precision=round(precision, 6),
        recall=round(recall, 6),
        detection_coverage=round(coverage, 6),
        scenario_comparisons=comparisons,
    )