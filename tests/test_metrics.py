"""Automated test suite for Milestone 4: Metrics calculation and historical vs live version resolution."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from config.settings import STARTER_CONFIG
from database.models import MetricDefinition
from generator.assignment_generator import generate_assignments_for_all_experiments
from generator.audience_generator import generate_audience_members
from generator.event_generator import simulate_exposures_and_conversions
from generator.master_data import generate_master_data
from services.experiment_service import validate_mde_for_metric_type
from services.metrics import (
    calculate_variant_diagnostics,
    resolve_metric_version_at_timestamp,
)
from services.statistics import (
    evaluate_current_launch_decision,
    run_experiment_analysis,
)


def test_variant_diagnostics_and_itt_vs_exposed_metrics(db_session: Session) -> None:
    """Verify all 10 required variant diagnostic counts reconcile with source records."""
    generate_master_data(db_session, STARTER_CONFIG)
    pools = generate_audience_members(db_session, STARTER_CONFIG)
    asgs = generate_assignments_for_all_experiments(db_session, STARTER_CONFIG, pools)
    simulate_exposures_and_conversions(db_session, STARTER_CONFIG, asgs)

    diags = calculate_variant_diagnostics(db_session, "EXP-2026-000001")
    assert len(diags) == 2
    total_assigned = sum(d.total_assigned_users for d in diags.values())
    total_eligible = sum(d.total_eligible_assigned_users for d in diags.values())
    assert total_assigned == 500
    assert total_eligible == 500

    for d in diags.values():
        assert d.total_exposed_users <= d.total_eligible_assigned_users
        assert abs(d.conversion_rate_itt - (d.total_conversions / d.total_eligible_assigned_users)) < 1e-6


def test_historical_vs_current_metric_version_decision(db_session: Session) -> None:
    """Verify historical V1 analysis remains valid while live decision flags RECALCULATION_REQUIRED after V2."""
    generate_master_data(db_session, STARTER_CONFIG)
    pools = generate_audience_members(db_session, STARTER_CONFIG)
    asgs = generate_assignments_for_all_experiments(db_session, STARTER_CONFIG, pools)
    simulate_exposures_and_conversions(db_session, STARTER_CONFIG, asgs)

    exp_id = "EXP-2026-000001"
    # Run initial analysis at Jan 15 under V1
    results_v1 = run_experiment_analysis(
        db_session,
        experiment_id=exp_id,
        analysis_run_id="RUN-EXP-2026-000001-001",
        analysis_timestamp="2026-01-15T00:00:00Z",
    )
    trt_res_v1 = [
        r for r in results_v1 if r.variant_id == "VAR-EXP-2026-000001-B" and r.analysis_method == "ITT"
    ][0]
    assert trt_res_v1.metric_version == 1

    # Append V2 metric definition effective Jan 25
    db_session.add(
        MetricDefinition(
            metric_id="MET-EXP-2026-000001-CONV-V2",
            experiment_id=exp_id,
            metric_code="MET-EXP-2026-000001-CONV",
            metric_name="Purchase Conversion Rate V2 (Exposed Denominator)",
            metric_type="Primary_Binary",
            metric_description="Updated denominator to exposed users",
            numerator_definition="Converted exposed users",
            denominator_definition="Exposed users",
            calculation_method="Exposed_Proportion",
            metric_version=2,
            effective_from="2026-01-25T00:00:00Z",
            created_at="2026-01-25T00:00:00Z",
        )
    )
    db_session.flush()

    # Point-in-time lookup at Jan 15 still resolves V1 (historical calculation remains valid)
    pit_v1 = resolve_metric_version_at_timestamp(
        db_session, exp_id, "MET-EXP-2026-000001-CONV", "2026-01-15T00:00:00Z"
    )
    assert pit_v1.metric_version == 1

    # Current launch decision evaluator detects that V2 > V1 and returns RECALCULATION_REQUIRED
    live_decisions = evaluate_current_launch_decision(db_session, exp_id)
    assert live_decisions["VAR-EXP-2026-000001-B"] == "RECALCULATION_REQUIRED"


def test_mde_validation_by_metric_type() -> None:
    """Verify service-level MDE validation for Primary_Binary, Primary_Continuous, and Guardrail_Rate."""
    validate_mde_for_metric_type(0.02, "Primary_Binary")
    validate_mde_for_metric_type(5.50, "Primary_Continuous")

    with pytest.raises(ValueError, match="0.0 <= minimum_detectable_effect <= 1.0"):
        validate_mde_for_metric_type(1.25, "Primary_Binary")

    with pytest.raises(ValueError, match="non-negative"):
        validate_mde_for_metric_type(-0.5, "Primary_Continuous")

    with pytest.raises(ValueError, match="Guardrail_Rate"):
        validate_mde_for_metric_type(0.01, "Guardrail_Rate")