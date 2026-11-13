"""Automated test suite for Milestone 4: Guardrail evaluation and 8-priority decision hierarchy."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from config.settings import STARTER_CONFIG
from generator.assignment_generator import generate_assignments_for_all_experiments
from generator.audience_generator import generate_audience_members
from generator.event_generator import simulate_exposures_and_conversions
from generator.master_data import generate_master_data
from services.guardrails import evaluate_guardrails_for_variant
from services.statistics import resolve_decision_status


def test_guardrail_breach_detection_on_experiment_3(db_session: Session) -> None:
    """Verify Experiment 3 (Aggressive Countdown Timer) triggers FAILED guardrail status on Refund Rate."""
    generate_master_data(db_session, STARTER_CONFIG)
    pools = generate_audience_members(db_session, STARTER_CONFIG)
    asgs = generate_assignments_for_all_experiments(db_session, STARTER_CONFIG, pools)
    simulate_exposures_and_conversions(db_session, STARTER_CONFIG, asgs)

    agg_status, items = evaluate_guardrails_for_variant(
        db_session, "EXP-2026-000003", "VAR-EXP-2026-000003-B"
    )
    assert agg_status == "FAILED"
    failed_items = [i for i in items if i.evaluation_status == "FAILED"]
    assert len(failed_items) >= 1


def test_insufficient_guardrail_data_status(db_session: Session) -> None:
    """Verify guardrail evaluator returns INSUFFICIENT_DATA when denominator is below threshold."""
    generate_master_data(db_session, STARTER_CONFIG)
    # Without assignments, denominator is 0 (< 30)
    agg_status, items = evaluate_guardrails_for_variant(
        db_session, "EXP-2026-000001", "VAR-EXP-2026-000001-B"
    )
    assert agg_status == "INSUFFICIENT_DATA"
    assert all(i.evaluation_status == "INSUFFICIENT_DATA" for i in items)


@pytest.mark.parametrize(
    "is_ctrl,data_hold,ver_mismatch,grd_status,p_val,effect,mde,expected_decision",
    [
        (True, False, False, "NOT_APPLICABLE", None, None, 0.02, "CONTROL_BASELINE"),
        (False, True, False, "PASSED", 0.001, 0.05, 0.02, "INVALID_DATA_HOLD"),
        (False, False, True, "PASSED", 0.001, 0.05, 0.02, "RECALCULATION_REQUIRED"),
        (
            False,
            False,
            False,
            "FAILED",
            0.001,
            0.05,
            0.02,
            "DO_NOT_LAUNCH_GUARDRAIL_BREACH",
        ),
        (
            False,
            False,
            False,
            "INSUFFICIENT_DATA",
            0.001,
            0.05,
            0.02,
            "INSUFFICIENT_GUARDRAIL_DATA",
        ),
        (
            False,
            False,
            False,
            "PASSED",
            0.120,
            0.05,
            0.02,
            "DO_NOT_LAUNCH_NO_SIGNIFICANT_LIFT",
        ),
        (
            False,
            False,
            False,
            "PASSED",
            0.005,
            0.012,
            0.02,
            "DO_NOT_LAUNCH_BELOW_MDE",
        ),
        (
            False,
            False,
            False,
            "WARNING",
            0.005,
            0.035,
            0.02,
            "HOLD_FOR_GUARDRAIL_REVIEW",
        ),
        (False, False, False, "PASSED", 0.005, 0.035, 0.02, "LAUNCH_TREATMENT"),
    ],
)
def test_strict_decision_precedence_hierarchy(
    is_ctrl: bool,
    data_hold: bool,
    ver_mismatch: bool,
    grd_status: str,
    p_val: float | None,
    effect: float | None,
    mde: float,
    expected_decision: str,
) -> None:
    """Verify all 9 outcomes in the decision precedence table."""
    actual = resolve_decision_status(
        is_control=is_ctrl,
        has_data_quality_or_srm_hold=data_hold,
        has_metric_version_mismatch=ver_mismatch,
        guardrail_status=grd_status,
        p_value=p_val,
        significance_level=0.05,
        treatment_effect=effect,
        minimum_detectable_effect=mde,
    )
    assert actual == expected_decision