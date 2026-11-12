"""Automated test suite for Milestone 1: Database schema, triggers, FKs, and ORM parity."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import database.connection as conn_module
from config.settings import DEFAULT_RANDOM_SEED, REFERENCE_EPOCH_ISO
from database.connection import verify_sqlite_version
from database.models import (
    Assignment,
    AudienceMember,
    Base,
    ConversionEvent,
    Experiment,
    ExperimentResult,
    ExposureEvent,
    MetricDefinition,
    Variant,
)


def _seed_base_experiment_and_variants(
    session: Session,
    exp_id: str = "EXP-2026-000001",
    primary_code: str = "MET-EXP-2026-000001-CONV",
    mde: float = 0.02,
    alpha: float = 0.05,
    metric_type: str = "Primary_Binary",
    calc_method: str = "ITT_Proportion",
) -> None:
    """Helper to seed a valid Draft experiment, Control/Treatment variants, and V1 primary metric."""
    exp = Experiment(
        experiment_id=exp_id,
        experiment_name="Checkout Funnel Redesign",
        description="Test simplified checkout layout",
        hypothesis="New layout increases checkout conversion by at least 2 percentage points",
        primary_metric_code=primary_code,
        minimum_detectable_effect=mde,
        significance_level=alpha,
        experiment_status="Draft",
        expected_allocation_ratio="50:50",
        start_date="2026-01-01T00:00:00Z",
        end_date="2026-01-31T23:59:59Z",
        conversion_window_days=7,
        random_seed=DEFAULT_RANDOM_SEED,
        created_at=REFERENCE_EPOCH_ISO,
        updated_at=REFERENCE_EPOCH_ISO,
    )
    var_a = Variant(
        variant_id=f"VAR-{exp_id}-A",
        experiment_id=exp_id,
        variant_name="A",
        variant_type="Control",
        allocation_percentage=50.0,
        description="Existing checkout experience",
        created_at=REFERENCE_EPOCH_ISO,
    )
    var_b = Variant(
        variant_id=f"VAR-{exp_id}-B",
        experiment_id=exp_id,
        variant_name="B",
        variant_type="Treatment",
        allocation_percentage=50.0,
        description="New streamlined checkout experience",
        created_at=REFERENCE_EPOCH_ISO,
    )
    met_v1 = MetricDefinition(
        metric_id=f"{primary_code}-V1",
        experiment_id=exp_id,
        metric_code=primary_code,
        metric_name="Checkout Conversion Rate",
        metric_type=metric_type,
        metric_description="Proportion of assigned users completing a valid purchase",
        numerator_definition="Distinct assigned users with valid Purchase conversion in window",
        denominator_definition="Total eligible assigned users (ITT)",
        calculation_method=calc_method,
        metric_version=1,
        effective_from="2026-01-01T00:00:00Z",
        created_at=REFERENCE_EPOCH_ISO,
    )
    session.add_all([exp, var_a, var_b, met_v1])
    session.flush()


def test_sqlite_runtime_version_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify SQLite runtime version check passes for >= 3.25.0 and fails cleanly below 3.25.0."""
    version = verify_sqlite_version()
    assert version >= (3, 25, 0)

    monkeypatch.setattr(conn_module.sqlite3, "sqlite_version_info", (3, 24, 0))
    with pytest.raises(RuntimeError, match="SQLite >= 3.25.0 is required"):
        verify_sqlite_version()


def test_schema_sql_and_orm_metadata_parity(db_session: Session) -> None:
    """Verify that all 11 operational tables and columns in schema.sql match Base.metadata."""
    rows = db_session.execute(
        text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    ).fetchall()
    db_tables = {row[0] for row in rows}
    orm_tables = set(Base.metadata.tables.keys())

    assert len(orm_tables) == 11
    assert db_tables == orm_tables
    assert "ground_truth" not in db_tables

    for table_name, orm_table in Base.metadata.tables.items():
        pragma_rows = db_session.execute(
            text(f"PRAGMA table_info({table_name})")
        ).fetchall()
        db_columns = {row[1] for row in pragma_rows}
        orm_columns = {col.name for col in orm_table.columns}
        assert db_columns == orm_columns, f"Column mismatch on table {table_name}"

    # Confirm removed fields do not exist
    metric_cols = {
        r[1]
        for r in db_session.execute(
            text("PRAGMA table_info(metric_definitions)")
        ).fetchall()
    }
    assert "effective_to" not in metric_cols
    assert "superseded_by_version" not in metric_cols
    assert "is_primary" not in metric_cols

    issue_cols = {
        r[1]
        for r in db_session.execute(
            text("PRAGMA table_info(experiment_issues)")
        ).fetchall()
    }
    assert "ground_truth_reference" not in issue_cols


def test_composite_referential_integrity(db_session: Session) -> None:
    """Verify composite FKs prevent cross-experiment or cross-user record mismatches."""
    _seed_base_experiment_and_variants(db_session, exp_id="EXP-2026-000001")
    _seed_base_experiment_and_variants(
        db_session,
        exp_id="EXP-2026-000002",
        primary_code="MET-EXP-2026-000002-CONV",
    )

    user1 = AudienceMember(
        user_id="USER-000001",
        user_segment="Returning",
        eligibility_status="Eligible",
        registration_date="2025-12-01T00:00:00Z",
        country_region="US-East",
        created_at=REFERENCE_EPOCH_ISO,
    )
    user2 = AudienceMember(
        user_id="USER-000002",
        user_segment="New",
        eligibility_status="Eligible",
        registration_date="2025-12-15T00:00:00Z",
        country_region="EU-West",
        created_at=REFERENCE_EPOCH_ISO,
    )
    db_session.add_all([user1, user2])
    db_session.flush()

    # 1. Assignment referencing a variant from a different experiment must fail
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            bad_asg = Assignment(
                assignment_id="ASG-EXP-2026-000001-USER-000001",
                experiment_id="EXP-2026-000001",
                user_id="USER-000001",
                variant_id="VAR-EXP-2026-000002-A",  # Belongs to EXP-2026-000002!
                assigned_at="2026-01-02T00:00:00Z",
                assignment_status="Assigned",
                randomization_seed=DEFAULT_RANDOM_SEED,
            )
            db_session.add(bad_asg)
            db_session.flush()

    # Valid assignment succeeds
    valid_asg = Assignment(
        assignment_id="ASG-EXP-2026-000001-USER-000001",
        experiment_id="EXP-2026-000001",
        user_id="USER-000001",
        variant_id="VAR-EXP-2026-000001-A",
        assigned_at="2026-01-02T00:00:00Z",
        assignment_status="Assigned",
        randomization_seed=DEFAULT_RANDOM_SEED,
    )
    db_session.add(valid_asg)
    db_session.flush()

    # 2. Exposure with mismatched variant or user for the referenced assignment must fail
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            bad_exp = ExposureEvent(
                exposure_id="EXPOS-2026-000001",
                experiment_id="EXP-2026-000001",
                assignment_id="ASG-EXP-2026-000001-USER-000001",
                user_id="USER-000001",
                variant_id="VAR-EXP-2026-000001-B",  # Assignment was for Variant A!
                exposure_timestamp="2026-01-02T01:00:00Z",
                exposure_status="Exposed",
                telemetry_status="Complete",
            )
            db_session.add(bad_exp)
            db_session.flush()

    # 3. Conversion with optional assignment_id belonging to a different user must fail
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            bad_conv = ConversionEvent(
                conversion_id="CONV-2026-000001",
                experiment_id="EXP-2026-000001",
                user_id="USER-000002",  # Mismatched user!
                assignment_id="ASG-EXP-2026-000001-USER-000001",
                conversion_type="Purchase",
                conversion_timestamp="2026-01-03T00:00:00Z",
                conversion_value=49.99,
                conversion_status="Valid",
            )
            db_session.add(bad_conv)
            db_session.flush()

    # Conversion with NULL assignment_id (optional FK) and valid experiment/user succeeds
    unlinked_conv = ConversionEvent(
        conversion_id="CONV-2026-000002",
        experiment_id="EXP-2026-000001",
        user_id="USER-000002",
        assignment_id=None,
        conversion_type="Purchase",
        conversion_timestamp="2026-01-03T00:00:00Z",
        conversion_value=25.00,
        conversion_status="Valid",
    )
    db_session.add(unlinked_conv)
    db_session.flush()


def test_single_control_variant_and_result_control_fk(db_session: Session) -> None:
    """Verify partial unique index blocks a 2nd Control variant and result FK enforces Control type."""
    _seed_base_experiment_and_variants(db_session, exp_id="EXP-2026-000001")

    # Adding a second Treatment variant ('C') succeeds
    var_c = Variant(
        variant_id="VAR-EXP-2026-000001-C",
        experiment_id="EXP-2026-000001",
        variant_name="C",
        variant_type="Treatment",
        allocation_percentage=25.0,
        description="Alternative treatment",
        created_at=REFERENCE_EPOCH_ISO,
    )
    db_session.add(var_c)
    db_session.flush()

    # Adding a second Control variant for the same experiment is rejected by idx_variants_single_control
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            second_control = Variant(
                variant_id="VAR-EXP-2026-000001-CTRL2",
                experiment_id="EXP-2026-000001",
                variant_name="Control_2",
                variant_type="Control",
                allocation_percentage=25.0,
                description="Illegal second control",
                created_at=REFERENCE_EPOCH_ISO,
            )
            db_session.add(second_control)
            db_session.flush()

    # Attempting to insert an ExperimentResult where control_variant_id is actually a Treatment variant fails
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            bad_ctrl_res = ExperimentResult(
                result_id="RES-RUN-EXP-2026-000001-001-VAR-EXP-2026-000001-C-MET-EXP-2026-000001-CONV-V1-ITT",
                analysis_run_id="RUN-EXP-2026-000001-001",
                experiment_id="EXP-2026-000001",
                variant_id="VAR-EXP-2026-000001-C",
                control_variant_id="VAR-EXP-2026-000001-B",  # B is Treatment, not Control!
                metric_id="MET-EXP-2026-000001-CONV-V1",
                metric_version=1,
                analysis_method="ITT",
                sample_size=500,
                numerator=60.0,
                denominator=500.0,
                metric_value=0.12,
                treatment_effect=0.02,
                relative_lift=0.20,
                standard_error=0.008,
                confidence_interval_lower=0.004,
                confidence_interval_upper=0.036,
                p_value=0.012,
                statistical_significance=1,
                guardrail_status="PASSED",
                decision_status="LAUNCH_TREATMENT",
                analysis_timestamp="2026-01-15T00:00:00Z",
            )
            db_session.add(bad_ctrl_res)
            db_session.flush()


def test_exact_lifecycle_state_machine(db_session: Session) -> None:
    """Verify only exact allowed lifecycle transitions succeed and shortcuts or returning to Draft fail."""
    _seed_base_experiment_and_variants(db_session, exp_id="EXP-2026-000001")
    exp = db_session.get(Experiment, "EXP-2026-000001")
    assert exp is not None

    # Disallowed shortcut Draft -> Running or Draft -> Archived must fail
    for invalid_target in ("Running", "Paused", "Completed", "Archived"):
        with pytest.raises(
            IntegrityError, match="Invalid experiment_status lifecycle transition"
        ):
            with db_session.begin_nested():
                db_session.execute(
                    text(
                        "UPDATE experiments SET experiment_status = :status WHERE experiment_id = 'EXP-2026-000001'"
                    ),
                    {"status": invalid_target},
                )

    # Valid path: Draft -> Ready -> Running -> Paused -> Running -> Completed -> Archived
    for next_status in (
        "Ready",
        "Running",
        "Paused",
        "Running",
        "Completed",
        "Archived",
    ):
        db_session.execute(
            text(
                "UPDATE experiments SET experiment_status = :status WHERE experiment_id = 'EXP-2026-000001'"
            ),
            {"status": next_status},
        )

    # Returning to Draft from Archived (or any non-Draft state) must fail
    with pytest.raises(IntegrityError, match="cannot return to Draft"):
        with db_session.begin_nested():
            db_session.execute(
                text(
                    "UPDATE experiments SET experiment_status = 'Draft' WHERE experiment_id = 'EXP-2026-000001'"
                )
            )

    # Archived is terminal: Archived -> Completed must fail
    with pytest.raises(IntegrityError, match="Archived is a terminal state"):
        with db_session.begin_nested():
            db_session.execute(
                text(
                    "UPDATE experiments SET experiment_status = 'Completed' WHERE experiment_id = 'EXP-2026-000001'"
                )
            )


def test_atomic_transition_and_parameter_modification_blocked(
    db_session: Session,
) -> None:
    """Verify MDE, significance_level, and primary_metric_code can only be edited while remaining in Draft."""
    _seed_base_experiment_and_variants(db_session, exp_id="EXP-2026-000001")

    # Editing MDE while staying in Draft succeeds
    db_session.execute(
        text(
            "UPDATE experiments SET minimum_detectable_effect = 0.025 WHERE experiment_id = 'EXP-2026-000001'"
        )
    )

    # Attempting to simultaneously transition Draft -> Ready AND modify MDE in a single UPDATE must fail
    with pytest.raises(
        IntegrityError,
        match="can only be modified while experiment_status remains in Draft",
    ):
        with db_session.begin_nested():
            db_session.execute(
                text(
                    "UPDATE experiments SET experiment_status = 'Ready', minimum_detectable_effect = 0.05 "
                    "WHERE experiment_id = 'EXP-2026-000001'"
                )
            )

    # Transition cleanly to Ready, then verify parameter edits fail in Ready, Running, Paused, Completed, Archived
    for status in ("Ready", "Running", "Paused", "Completed", "Archived"):
        db_session.execute(
            text(
                "UPDATE experiments SET experiment_status = :st WHERE experiment_id = 'EXP-2026-000001'"
            ),
            {"st": status},
        )
        with pytest.raises(
            IntegrityError,
            match="can only be modified while experiment_status remains in Draft",
        ):
            with db_session.begin_nested():
                db_session.execute(
                    text(
                        "UPDATE experiments SET significance_level = 0.01 WHERE experiment_id = 'EXP-2026-000001'"
                    )
                )


def test_primary_metric_rejects_guardrail_rate_and_enforces_mde_scale(
    db_session: Session,
) -> None:
    """Verify primary metric cannot be Guardrail_Rate and Primary_Binary MDE must be in [0.0, 1.0]."""
    _seed_base_experiment_and_variants(db_session, exp_id="EXP-2026-000001")

    # Setting MDE > 1.0 on an experiment with a Primary_Binary metric must fail
    with pytest.raises(
        IntegrityError,
        match="Primary_Binary metrics require 0.0 <= minimum_detectable_effect <= 1.0",
    ):
        with db_session.begin_nested():
            db_session.execute(
                text(
                    "UPDATE experiments SET minimum_detectable_effect = 1.5 WHERE experiment_id = 'EXP-2026-000001'"
                )
            )

    # Creating an experiment whose primary_metric_code is registered as Guardrail_Rate must fail
    exp2 = Experiment(
        experiment_id="EXP-2026-000002",
        experiment_name="Guardrail Misconfiguration Test",
        description="Desc",
        hypothesis="Hyp",
        primary_metric_code="MET-EXP-2026-000002-REFUND",
        minimum_detectable_effect=0.01,
        significance_level=0.05,
        experiment_status="Draft",
        expected_allocation_ratio="50:50",
        start_date="2026-01-01T00:00:00Z",
        end_date="2026-01-31T23:59:59Z",
        conversion_window_days=7,
        random_seed=DEFAULT_RANDOM_SEED,
        created_at=REFERENCE_EPOCH_ISO,
        updated_at=REFERENCE_EPOCH_ISO,
    )
    db_session.add(exp2)
    db_session.flush()

    with pytest.raises(
        IntegrityError,
        match="experiment primary_metric_code must be Primary_Binary or Primary_Continuous, not Guardrail_Rate",
    ):
        with db_session.begin_nested():
            bad_primary = MetricDefinition(
                metric_id="MET-EXP-2026-000002-REFUND-V1",
                experiment_id="EXP-2026-000002",
                metric_code="MET-EXP-2026-000002-REFUND",
                metric_name="Refund Rate",
                metric_type="Guardrail_Rate",
                metric_description="Refund rate",
                numerator_definition="Refunds",
                denominator_definition="Assigned users",
                calculation_method="ITT_Proportion",
                metric_version=1,
                effective_from="2026-01-01T00:00:00Z",
                created_at=REFERENCE_EPOCH_ISO,
            )
            db_session.add(bad_primary)
            db_session.flush()

    # Transitioning EXP-2026-000002 out of Draft without a valid Primary_Binary/Primary_Continuous metric fails
    with pytest.raises(
        IntegrityError,
        match="primary_metric_code must reference an existing Primary_Binary or Primary_Continuous metric definition",
    ):
        with db_session.begin_nested():
            db_session.execute(
                text(
                    "UPDATE experiments SET experiment_status = 'Ready' WHERE experiment_id = 'EXP-2026-000002'"
                )
            )

    # Primary_Continuous metric allows MDE > 1.0 in native units (e.g. $5.00 revenue lift)
    _seed_base_experiment_and_variants(
        db_session,
        exp_id="EXP-2026-000003",
        primary_code="MET-EXP-2026-000003-REV",
        mde=5.00,
        metric_type="Primary_Continuous",
        calc_method="ITT_Mean_Value",
    )
    db_session.execute(
        text(
            "UPDATE experiments SET experiment_status = 'Ready' WHERE experiment_id = 'EXP-2026-000003'"
        )
    )


def test_metric_version_append_only_and_lead_window_lookup(
    db_session: Session,
) -> None:
    """Verify metric_definitions is append-only, enforces monotonic versions, and supports LEAD(effective_from)."""
    _seed_base_experiment_and_variants(db_session, exp_id="EXP-2026-000001")

    # Updating or deleting V1 must be blocked by immutability triggers
    with pytest.raises(
        IntegrityError, match="metric_definitions is strictly append-only and immutable"
    ):
        with db_session.begin_nested():
            db_session.execute(
                text(
                    "UPDATE metric_definitions SET metric_name = 'Modified' "
                    "WHERE metric_id = 'MET-EXP-2026-000001-CONV-V1'"
                )
            )

    with pytest.raises(
        IntegrityError, match="metric_definitions is strictly append-only and immutable"
    ):
        with db_session.begin_nested():
            db_session.execute(
                text(
                    "DELETE FROM metric_definitions WHERE metric_id = 'MET-EXP-2026-000001-CONV-V1'"
                )
            )

    # Inserting version 3 (skipping version 2) or version 2 with an earlier/equal effective_from must fail
    with pytest.raises(
        IntegrityError,
        match="New metric_version must increment prior version by 1 and have a strictly later effective_from timestamp",
    ):
        with db_session.begin_nested():
            db_session.add(
                MetricDefinition(
                    metric_id="MET-EXP-2026-000001-CONV-V3",
                    experiment_id="EXP-2026-000001",
                    metric_code="MET-EXP-2026-000001-CONV",
                    metric_name="Conversion V3",
                    metric_type="Primary_Binary",
                    metric_description="Skipped version",
                    numerator_definition="Num",
                    denominator_definition="Denom",
                    calculation_method="ITT_Proportion",
                    metric_version=3,
                    effective_from="2026-01-10T00:00:00Z",
                    created_at=REFERENCE_EPOCH_ISO,
                )
            )
            db_session.flush()

    with pytest.raises(
        IntegrityError,
        match="New metric_version must increment prior version by 1 and have a strictly later effective_from timestamp",
    ):
        with db_session.begin_nested():
            db_session.add(
                MetricDefinition(
                    metric_id="MET-EXP-2026-000001-CONV-V2",
                    experiment_id="EXP-2026-000001",
                    metric_code="MET-EXP-2026-000001-CONV",
                    metric_name="Conversion V2",
                    metric_type="Primary_Binary",
                    metric_description="Same timestamp",
                    numerator_definition="Num",
                    denominator_definition="Denom",
                    calculation_method="ITT_Proportion",
                    metric_version=2,
                    effective_from="2026-01-01T00:00:00Z",  # Not strictly later than V1!
                    created_at=REFERENCE_EPOCH_ISO,
                )
            )
            db_session.flush()

    # Valid V2 insert succeeds
    db_session.add(
        MetricDefinition(
            metric_id="MET-EXP-2026-000001-CONV-V2",
            experiment_id="EXP-2026-000001",
            metric_code="MET-EXP-2026-000001-CONV",
            metric_name="Conversion V2 (Exposed Only)",
            metric_type="Primary_Binary",
            metric_description="Updated denominator to exposed users",
            numerator_definition="Converted exposed users",
            denominator_definition="Exposed users",
            calculation_method="Exposed_Proportion",
            metric_version=2,
            effective_from="2026-01-10T00:00:00Z",
            created_at="2026-01-10T00:00:00Z",
        )
    )
    db_session.flush()

    # Verify point-in-time resolution via LEAD(effective_from)
    pit_query = text(
        """
        WITH version_windows AS (
            SELECT
                metric_id,
                metric_version,
                effective_from,
                LEAD(effective_from) OVER (
                    PARTITION BY experiment_id, metric_code
                    ORDER BY metric_version ASC
                ) AS derived_effective_to
            FROM metric_definitions
            WHERE experiment_id = :exp_id AND metric_code = :code
        )
        SELECT metric_version
        FROM version_windows
        WHERE effective_from <= :ts
          AND (derived_effective_to IS NULL OR :ts < derived_effective_to)
        """
    )

    v_at_jan05 = db_session.execute(
        pit_query,
        {
            "exp_id": "EXP-2026-000001",
            "code": "MET-EXP-2026-000001-CONV",
            "ts": "2026-01-05T12:00:00Z",
        },
    ).scalar_one()
    assert v_at_jan05 == 1

    v_at_jan12 = db_session.execute(
        pit_query,
        {
            "exp_id": "EXP-2026-000001",
            "code": "MET-EXP-2026-000001-CONV",
            "ts": "2026-01-12T00:00:00Z",
        },
    ).scalar_one()
    assert v_at_jan12 == 2


def test_experiment_results_check_constraints_immutability_and_significance_trigger(
    db_session: Session,
) -> None:
    """Verify Control vs Treatment CHECK constraints, stored significance trigger, and immutability."""
    _seed_base_experiment_and_variants(
        db_session, exp_id="EXP-2026-000001", alpha=0.05
    )

    # 1. Valid Control row (all 7 comparative fields NULL)
    ctrl_res = ExperimentResult(
        result_id="RES-RUN-EXP-2026-000001-001-VAR-EXP-2026-000001-A-MET-EXP-2026-000001-CONV-V1-ITT",
        analysis_run_id="RUN-EXP-2026-000001-001",
        experiment_id="EXP-2026-000001",
        variant_id="VAR-EXP-2026-000001-A",
        control_variant_id="VAR-EXP-2026-000001-A",
        metric_id="MET-EXP-2026-000001-CONV-V1",
        metric_version=1,
        analysis_method="ITT",
        sample_size=2500,
        numerator=250.0,
        denominator=2500.0,
        metric_value=0.10,
        treatment_effect=None,
        relative_lift=None,
        standard_error=None,
        confidence_interval_lower=None,
        confidence_interval_upper=None,
        p_value=None,
        statistical_significance=None,
        guardrail_status="NOT_APPLICABLE",
        decision_status="CONTROL_BASELINE",
        analysis_timestamp="2026-01-15T00:00:00Z",
    )
    db_session.add(ctrl_res)
    db_session.flush()

    # 2. Control row with a non-null comparative field must fail CHECK
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            bad_ctrl = ExperimentResult(
                result_id="RES-RUN-EXP-2026-000001-002-VAR-EXP-2026-000001-A-MET-EXP-2026-000001-CONV-V1-ITT",
                analysis_run_id="RUN-EXP-2026-000001-002",
                experiment_id="EXP-2026-000001",
                variant_id="VAR-EXP-2026-000001-A",
                control_variant_id="VAR-EXP-2026-000001-A",
                metric_id="MET-EXP-2026-000001-CONV-V1",
                metric_version=1,
                analysis_method="ITT",
                sample_size=2500,
                numerator=250.0,
                denominator=2500.0,
                metric_value=0.10,
                treatment_effect=0.0,  # Must be NULL for Control!
                relative_lift=None,
                standard_error=None,
                confidence_interval_lower=None,
                confidence_interval_upper=None,
                p_value=None,
                statistical_significance=None,
                guardrail_status="NOT_APPLICABLE",
                decision_status="CONTROL_BASELINE",
                analysis_timestamp="2026-01-15T00:00:00Z",
            )
            db_session.add(bad_ctrl)
            db_session.flush()

    # 3. Treatment row with inverted CI bounds (confidence_interval_lower > treatment_effect) must fail CHECK
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            bad_ci = ExperimentResult(
                result_id="RES-RUN-EXP-2026-000001-001-VAR-EXP-2026-000001-B-MET-EXP-2026-000001-CONV-V1-ITT",
                analysis_run_id="RUN-EXP-2026-000001-001",
                experiment_id="EXP-2026-000001",
                variant_id="VAR-EXP-2026-000001-B",
                control_variant_id="VAR-EXP-2026-000001-A",
                metric_id="MET-EXP-2026-000001-CONV-V1",
                metric_version=1,
                analysis_method="ITT",
                sample_size=2500,
                numerator=310.0,
                denominator=2500.0,
                metric_value=0.124,
                treatment_effect=0.024,
                relative_lift=0.24,
                standard_error=0.0089,
                confidence_interval_lower=0.030,  # > treatment_effect (0.024)!
                confidence_interval_upper=0.041,
                p_value=0.007,
                statistical_significance=1,
                guardrail_status="PASSED",
                decision_status="LAUNCH_TREATMENT",
                analysis_timestamp="2026-01-15T00:00:00Z",
            )
            db_session.add(bad_ci)
            db_session.flush()

    # 4. Treatment row with inconsistent statistical_significance (p_value=0.007 < 0.05 but sig=0) must fail trigger
    with pytest.raises(
        IntegrityError,
        match="Inconsistent statistical_significance: must be 1 when p_value < experiments.significance_level",
    ):
        with db_session.begin_nested():
            bad_sig = ExperimentResult(
                result_id="RES-RUN-EXP-2026-000001-001-VAR-EXP-2026-000001-B-MET-EXP-2026-000001-CONV-V1-ITT",
                analysis_run_id="RUN-EXP-2026-000001-001",
                experiment_id="EXP-2026-000001",
                variant_id="VAR-EXP-2026-000001-B",
                control_variant_id="VAR-EXP-2026-000001-A",
                metric_id="MET-EXP-2026-000001-CONV-V1",
                metric_version=1,
                analysis_method="ITT",
                sample_size=2500,
                numerator=310.0,
                denominator=2500.0,
                metric_value=0.124,
                treatment_effect=0.024,
                relative_lift=0.24,
                standard_error=0.0089,
                confidence_interval_lower=0.0065,
                confidence_interval_upper=0.0415,
                p_value=0.007,
                statistical_significance=0,  # Contradicts p_value < 0.05!
                guardrail_status="PASSED",
                decision_status="LAUNCH_TREATMENT",
                analysis_timestamp="2026-01-15T00:00:00Z",
            )
            db_session.add(bad_sig)
            db_session.flush()

    # 5. Valid Treatment row succeeds
    valid_trt = ExperimentResult(
        result_id="RES-RUN-EXP-2026-000001-001-VAR-EXP-2026-000001-B-MET-EXP-2026-000001-CONV-V1-ITT",
        analysis_run_id="RUN-EXP-2026-000001-001",
        experiment_id="EXP-2026-000001",
        variant_id="VAR-EXP-2026-000001-B",
        control_variant_id="VAR-EXP-2026-000001-A",
        metric_id="MET-EXP-2026-000001-CONV-V1",
        metric_version=1,
        analysis_method="ITT",
        sample_size=2500,
        numerator=310.0,
        denominator=2500.0,
        metric_value=0.124,
        treatment_effect=0.024,
        relative_lift=0.24,
        standard_error=0.0089,
        confidence_interval_lower=0.0065,
        confidence_interval_upper=0.0415,
        p_value=0.007,
        statistical_significance=1,
        guardrail_status="PASSED",
        decision_status="LAUNCH_TREATMENT",
        analysis_timestamp="2026-01-15T00:00:00Z",
    )
    db_session.add(valid_trt)
    db_session.flush()

    # 6. Once results exist, modifying MDE even while experiment is still in Draft is blocked
    with pytest.raises(
        IntegrityError,
        match="Predeclared parameters cannot be modified after analysis results have been recorded",
    ):
        with db_session.begin_nested():
            db_session.execute(
                text(
                    "UPDATE experiments SET minimum_detectable_effect = 0.03 WHERE experiment_id = 'EXP-2026-000001'"
                )
            )

    # 7. Updating or deleting experiment_results is blocked by immutability triggers
    with pytest.raises(
        IntegrityError, match="experiment_results is strictly append-only and immutable"
    ):
        with db_session.begin_nested():
            db_session.execute(
                text(
                    "UPDATE experiment_results SET p_value = 0.04 "
                    "WHERE result_id = 'RES-RUN-EXP-2026-000001-001-VAR-EXP-2026-000001-B-MET-EXP-2026-000001-CONV-V1-ITT'"
                )
            )

    with pytest.raises(
        IntegrityError, match="experiment_results is strictly append-only and immutable"
    ):
        with db_session.begin_nested():
            db_session.execute(
                text(
                    "DELETE FROM experiment_results "
                    "WHERE result_id = 'RES-RUN-EXP-2026-000001-001-VAR-EXP-2026-000001-B-MET-EXP-2026-000001-CONV-V1-ITT'"
                )
            )