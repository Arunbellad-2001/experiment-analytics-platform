"""Step 11: Deliberate injection of all 5 required negative anomaly scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from config.settings import DEFAULT_RANDOM_SEED, DatasetScaleConfig
from database.models import (
    Assignment,
    ConversionEvent,
    ExposureEvent,
    MetricDefinition,
)


@dataclass(frozen=True)
class InjectedAnomalySpec:
    """Metadata describing a deliberately injected assessment scenario (for ground-truth generation)."""

    scenario_id: str
    experiment_id: str
    affected_entity: str
    affected_record_id: str
    expected_anomaly_type: str
    expected_detection_result: str
    expected_decision: str
    generation_rule: str


def inject_labelled_anomalies(
    session: Session,
    config: DatasetScaleConfig,
) -> List[InjectedAnomalySpec]:
    """Inject all 5 required negative edge cases into designated experiments."""
    injected_specs: List[InjectedAnomalySpec] = []

    # Host experiment for Edge Cases 1, 2, 3, and 4 is EXP-2026-000005
    host_exp_id = "EXP-2026-000005"
    # Host experiment for Edge Case 5 (metric version change after results) must be distinct from host_exp_id
    # so Priority 2 (RECALCULATION_REQUIRED) is evaluated independently of Priority 1 (INVALID_DATA_HOLD):
    # - In Starter mode (5 experiments): EXP-2026-000004
    # - In Full mode (10 experiments): EXP-2026-000010
    version_exp_id = (
        "EXP-2026-000004"
        if config.experiment_count <= 5
        else f"EXP-2026-{config.experiment_count:06d}"
    )

    host_assignments = list(
        session.scalars(
            select(Assignment)
            .where(
                Assignment.experiment_id == host_exp_id,
                Assignment.assignment_status == "Assigned",
            )
            .order_by(Assignment.assignment_id.asc())
        ).all()
    )
    if len(host_assignments) < 5:
        return injected_specs

    # -------------------------------------------------------------------------
    # Edge Case 1: User assigned to multiple variants within the same experiment
    # -------------------------------------------------------------------------
    target_asg_1 = host_assignments[0]
    other_variant_id = (
        f"VAR-{host_exp_id}-B"
        if target_asg_1.variant_id.endswith("-A")
        else f"VAR-{host_exp_id}-A"
    )
    dup_assignment_id = f"{target_asg_1.assignment_id}-DUP"

    dup_asg = Assignment(
        assignment_id=dup_assignment_id,
        experiment_id=host_exp_id,
        user_id=target_asg_1.user_id,
        variant_id=other_variant_id,
        assigned_at="2026-01-03T12:00:00Z",
        assignment_status="Duplicate_Anomaly",
        randomization_seed=DEFAULT_RANDOM_SEED,
    )
    session.add(dup_asg)
    injected_specs.append(
        InjectedAnomalySpec(
            scenario_id="GT-2026-0001",
            experiment_id=host_exp_id,
            affected_entity="assignments",
            affected_record_id=target_asg_1.user_id,
            expected_anomaly_type="DUPLICATE_ASSIGNMENT",
            expected_detection_result="DETECTED",
            expected_decision="INVALID_DATA_HOLD",
            generation_rule=(
                f"Assigned user {target_asg_1.user_id} to both {target_asg_1.variant_id} "
                f"and {other_variant_id} in {host_exp_id}."
            ),
        )
    )

    # -------------------------------------------------------------------------
    # Edge Case 2: Exposure before assignment
    # -------------------------------------------------------------------------
    target_asg_2 = host_assignments[1]
    early_exposure_id = "EXPOS-2026-999001"
    early_exp = ExposureEvent(
        exposure_id=early_exposure_id,
        experiment_id=host_exp_id,
        assignment_id=target_asg_2.assignment_id,
        user_id=target_asg_2.user_id,
        variant_id=target_asg_2.variant_id,
        exposure_timestamp="2025-12-31T23:00:00Z",
        exposure_status="Invalid_Order",
        telemetry_status="Complete",
    )
    session.add(early_exp)
    injected_specs.append(
        InjectedAnomalySpec(
            scenario_id="GT-2026-0002",
            experiment_id=host_exp_id,
            affected_entity="exposure_events",
            affected_record_id=early_exposure_id,
            expected_anomaly_type="EXPOSURE_BEFORE_ASSIGNMENT",
            expected_detection_result="DETECTED",
            expected_decision="INVALID_DATA_HOLD",
            generation_rule=(
                f"Inserted exposure {early_exposure_id} at 2025-12-31T23:00:00Z prior to "
                f"assignment {target_asg_2.assignment_id} ({target_asg_2.assigned_at})."
            ),
        )
    )

    # -------------------------------------------------------------------------
    # Edge Case 3: Conversion outside configured conversion outcome window
    # -------------------------------------------------------------------------
    target_asg_3 = host_assignments[2]
    late_conversion_id = "CONV-2026-999001"
    late_conv = ConversionEvent(
        conversion_id=late_conversion_id,
        experiment_id=host_exp_id,
        user_id=target_asg_3.user_id,
        assignment_id=target_asg_3.assignment_id,
        conversion_type="Purchase",
        conversion_timestamp="2026-02-20T00:00:00Z",
        conversion_value=89.50,
        conversion_status="Outside_Window",
    )
    session.add(late_conv)
    injected_specs.append(
        InjectedAnomalySpec(
            scenario_id="GT-2026-0003",
            experiment_id=host_exp_id,
            affected_entity="conversion_events",
            affected_record_id=late_conversion_id,
            expected_anomaly_type="OUTCOME_WINDOW_VIOLATION",
            expected_detection_result="DETECTED",
            expected_decision="INVALID_DATA_HOLD",
            generation_rule=(
                f"Inserted conversion {late_conversion_id} at 2026-02-20T00:00:00Z outside "
                f"the 7-day conversion window of {host_exp_id}."
            ),
        )
    )

    # -------------------------------------------------------------------------
    # Edge Case 4: Sample Ratio Mismatch (62:38 skew on EXP-2026-000005 vs 50:50 expected)
    # -------------------------------------------------------------------------
    injected_specs.append(
        InjectedAnomalySpec(
            scenario_id="GT-2026-0004",
            experiment_id=host_exp_id,
            affected_entity="experiments",
            affected_record_id=host_exp_id,
            expected_anomaly_type="SRM_DETECTED",
            expected_detection_result="DETECTED",
            expected_decision="INVALID_DATA_HOLD",
            generation_rule=(
                f"Allocated eligible users in {host_exp_id} using 62:38 probabilities "
                "against predeclared 50:50 expected allocation ratio."
            ),
        )
    )

    # -------------------------------------------------------------------------
    # Edge Case 5: Metric definition changes after results have been calculated
    # -------------------------------------------------------------------------
    primary_code = f"MET-{version_exp_id}-CONV"
    new_metric_id = f"{primary_code}-V2"
    v2_metric = MetricDefinition(
        metric_id=new_metric_id,
        experiment_id=version_exp_id,
        metric_code=primary_code,
        metric_name="Purchase Conversion Rate (V2 Exposed-Only Definition)",
        metric_type="Primary_Binary",
        metric_description="Updated metric version requiring exposed denominator after V1 results were recorded",
        numerator_definition="Distinct exposed users with valid Purchase conversion in window",
        denominator_definition="Total exposed users (Exposed_Proportion)",
        calculation_method="Exposed_Proportion",
        metric_version=2,
        effective_from="2026-01-25T00:00:00Z",
        created_at="2026-01-25T00:00:00Z",
    )
    session.add(v2_metric)
    injected_specs.append(
        InjectedAnomalySpec(
            scenario_id="GT-2026-0005",
            experiment_id=version_exp_id,
            affected_entity="metric_definitions",
            affected_record_id=new_metric_id,
            expected_anomaly_type="METRIC_VERSION_MISMATCH",
            expected_detection_result="DETECTED",
            expected_decision="RECALCULATION_REQUIRED",
            generation_rule=(
                f"Appended metric_version=2 ({new_metric_id}) effective 2026-01-25T00:00:00Z "
                f"after V1 ExperimentResult snapshot was recorded at 2026-01-20T00:00:00Z."
            ),
        )
    )

    session.flush()
    return injected_specs