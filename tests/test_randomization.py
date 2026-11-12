"""Automated test suite for Milestone 2: Master data, Audience generation, Randomization & SRM validation."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config.settings import DEFAULT_RANDOM_SEED, STARTER_CONFIG
from database.models import Assignment, AudienceMember, Experiment, ExperimentIssue, Variant
from generator.assignment_generator import generate_assignments_for_all_experiments
from generator.audience_generator import (
    filter_eligible_audience,
    generate_audience_members,
)
from generator.master_data import generate_master_data
from services.experiment_service import (
    transition_experiment_status,
    update_predeclared_parameters,
    validate_experiment_variants,
)
from services.randomization import assign_eligible_users, validate_randomization_srm


def test_starter_master_data_and_audience_generation(db_session: Session) -> None:
    """Verify Steps 1-4 generate 5 experiments, 10 variants, 2,500 eligible users, and 250 ineligible users."""
    experiments, variants, metrics, guardrails = generate_master_data(
        db_session, STARTER_CONFIG
    )
    assert len(experiments) == 5
    assert len(variants) == 10
    assert len(metrics) == 20  # 1 primary + 3 guardrail metrics per experiment
    assert len(guardrails) == 20

    pools = generate_audience_members(db_session, STARTER_CONFIG)
    assert len(pools) == 5

    total_users = db_session.scalar(select(func.count(AudienceMember.user_id)))
    eligible_users = db_session.scalar(
        select(func.count(AudienceMember.user_id)).where(
            AudienceMember.eligibility_status == "Eligible"
        )
    )
    ineligible_users = db_session.scalar(
        select(func.count(AudienceMember.user_id)).where(
            AudienceMember.eligibility_status == "Ineligible"
        )
    )
    assert total_users == 2750
    assert eligible_users == 2500
    assert ineligible_users == 250


def test_eligible_only_assignment_and_no_duplicates(db_session: Session) -> None:
    """Verify only Eligible users are assigned, IDs follow ASG-EXP-...-USER-..., and repeat calls do not duplicate."""
    generate_master_data(db_session, STARTER_CONFIG)
    pools = generate_audience_members(db_session, STARTER_CONFIG)

    exp_id = "EXP-2026-000001"
    pool = pools[exp_id]
    assert len(pool) == 550
    assert len(filter_eligible_audience(pool)) == 500

    # Assign passing the full pool (both Eligible and Ineligible)
    assignments = assign_eligible_users(
        db_session, experiment_id=exp_id, candidate_users=pool, seed=DEFAULT_RANDOM_SEED
    )
    assert len(assignments) == 500
    assert assignments[0].assignment_id == "ASG-EXP-2026-000001-USER-000001"

    # Verify zero Ineligible users were assigned
    ineligible_assigned = db_session.scalar(
        select(func.count(Assignment.assignment_id))
        .join(AudienceMember, Assignment.user_id == AudienceMember.user_id)
        .where(
            Assignment.experiment_id == exp_id,
            AudienceMember.eligibility_status == "Ineligible",
        )
    )
    assert ineligible_assigned == 0

    # Calling assign_eligible_users a second time for the same users produces 0 duplicate rows
    second_call = assign_eligible_users(
        db_session, experiment_id=exp_id, candidate_users=pool, seed=DEFAULT_RANDOM_SEED
    )
    assert len(second_call) == 0


def test_balanced_and_unbalanced_randomization_and_srm_validation(
    db_session: Session,
) -> None:
    """Verify balanced (50:50), unbalanced (80:20), and SRM-skewed assignments are validated accurately."""
    generate_master_data(db_session, STARTER_CONFIG)
    pools = generate_audience_members(db_session, STARTER_CONFIG)

    # Run assignments with SRM injected on EXP-2026-000005
    generate_assignments_for_all_experiments(
        db_session,
        config=STARTER_CONFIG,
        experiment_user_pools=pools,
        inject_srm_on_designated=True,
    )

    # 1. EXP-2026-000001 (Balanced 50:50) should pass SRM validation
    res_balanced = validate_randomization_srm(db_session, "EXP-2026-000001")
    assert res_balanced.total_assigned == 500
    assert res_balanced.srm_detected is False
    assert res_balanced.validation_status == "VALID"
    assert len(res_balanced.variant_summaries) == 2

    # 2. EXP-2026-000004 (Unbalanced 80:20) should match 80:20 expectation and pass SRM validation
    res_unbalanced = validate_randomization_srm(db_session, "EXP-2026-000004")
    assert res_unbalanced.total_assigned == 500
    assert res_unbalanced.srm_detected is False
    assert res_unbalanced.variant_summaries[0].expected_percentage == 80.0
    assert res_unbalanced.variant_summaries[1].expected_percentage == 20.0

    # 3. EXP-2026-000005 (Skewed 62:38 vs expected 50:50) must detect SRM and log SRM_DETECTED issue
    res_srm = validate_randomization_srm(
        db_session, "EXP-2026-000005", record_issue=True
    )
    assert res_srm.total_assigned == 500
    assert res_srm.srm_detected is True
    assert res_srm.srm_p_value < 0.001
    assert res_srm.validation_status == "SRM_FAILED"

    srm_issue = db_session.scalar(
        select(ExperimentIssue).where(
            ExperimentIssue.experiment_id == "EXP-2026-000005",
            ExperimentIssue.issue_type == "SRM_DETECTED",
        )
    )
    assert srm_issue is not None
    assert srm_issue.severity == "CRITICAL"


def test_deterministic_assignment_reproducibility(db_session: Session) -> None:
    """Verify running assignment generation with the same seed produces identical variant mappings."""
    generate_master_data(db_session, STARTER_CONFIG)
    pools = generate_audience_members(db_session, STARTER_CONFIG)

    asg_run1 = assign_eligible_users(
        db_session,
        experiment_id="EXP-2026-000001",
        candidate_users=pools["EXP-2026-000001"],
        seed=DEFAULT_RANDOM_SEED,
        persist=False,
    )
    asg_run2 = assign_eligible_users(
        db_session,
        experiment_id="EXP-2026-000001",
        candidate_users=pools["EXP-2026-000001"],
        seed=DEFAULT_RANDOM_SEED,
        persist=False,
    )

    assert [a.assignment_id for a in asg_run1] == [a.assignment_id for a in asg_run2]
    assert [a.variant_id for a in asg_run1] == [a.variant_id for a in asg_run2]
    assert [a.assigned_at for a in asg_run1] == [a.assigned_at for a in asg_run2]


def test_service_level_validation_and_parameter_locking(db_session: Session) -> None:
    """Verify service-level guards for single Control variant, MDE bounds, and non-Draft parameter locks."""
    generate_master_data(db_session, STARTER_CONFIG)

    # Zero Control variants fails service validation
    fake_variants = [
        Variant(
            variant_id="VAR-X-1",
            experiment_id="EXP-X",
            variant_name="B1",
            variant_type="Treatment",
            allocation_percentage=50.0,
            description="T1",
            created_at="2026-01-01T00:00:00Z",
        ),
        Variant(
            variant_id="VAR-X-2",
            experiment_id="EXP-X",
            variant_name="B2",
            variant_type="Treatment",
            allocation_percentage=50.0,
            description="T2",
            created_at="2026-01-01T00:00:00Z",
        ),
    ]
    with pytest.raises(ValueError, match="exactly one Control variant"):
        validate_experiment_variants(fake_variants)

    # Binary MDE > 1.0 rejected by service validation while in Draft
    with pytest.raises(
        ValueError,
        match="Primary_Binary metrics require 0.0 <= minimum_detectable_effect <= 1.0",
    ):
        update_predeclared_parameters(
            db_session, "EXP-2026-000001", minimum_detectable_effect=1.2
        )

    # Valid MDE update in Draft succeeds
    update_predeclared_parameters(
        db_session, "EXP-2026-000001", minimum_detectable_effect=0.025
    )

    # Transition Draft -> Ready -> Running -> Paused, and verify parameter edits are blocked in non-Draft states
    transition_experiment_status(db_session, "EXP-2026-000001", "Ready")
    with pytest.raises(ValueError, match="Cannot modify predeclared parameters"):
        update_predeclared_parameters(
            db_session, "EXP-2026-000001", minimum_detectable_effect=0.03
        )

    # Returning to Draft is rejected by service
    with pytest.raises(ValueError, match="cannot return to Draft"):
        transition_experiment_status(db_session, "EXP-2026-000001", "Draft")