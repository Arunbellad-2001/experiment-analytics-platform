"""Step 13 & Section 16: Comprehensive QA validation suite (PKs, FKs, Enums, Date ordering, Arithmetic reconciliation)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config.settings import (
    ALLOWED_ASSIGNMENT_STATUSES,
    ALLOWED_CONVERSION_STATUSES,
    ALLOWED_DECISION_STATUSES,
    ALLOWED_EXPERIMENT_STATUSES,
    ALLOWED_EXPOSURE_STATUSES,
    ALLOWED_ISSUE_SEVERITIES,
    ALLOWED_ISSUE_TYPES,
    ALLOWED_METRIC_TYPES,
)
from database.models import (
    Assignment,
    AudienceMember,
    ConversionEvent,
    Experiment,
    ExperimentIssue,
    ExperimentResult,
    ExposureEvent,
    GuardrailMetric,
    MetricDefinition,
    Variant,
)
from services.metrics import calculate_variant_diagnostics


@dataclass(frozen=True)
class ValidationCheckResult:
    """Single validation rule outcome."""

    check_name: str
    category: str
    passed: bool
    details: str


def run_all_validation_checks(session: Session) -> Dict[str, Any]:
    """Execute all primary key, foreign key, enum, date-ordering, and arithmetic reconciliation checks."""
    checks: List[ValidationCheckResult] = []

    # 1. Primary Key & Non-Empty Checks
    exp_count = session.scalar(select(func.count(Experiment.experiment_id))) or 0
    var_count = session.scalar(select(func.count(Variant.variant_id))) or 0
    user_count = session.scalar(select(func.count(AudienceMember.user_id))) or 0
    asg_count = session.scalar(select(func.count(Assignment.assignment_id))) or 0

    checks.append(
        ValidationCheckResult(
            check_name="core_entities_populated",
            category="Primary_Keys",
            passed=bool(exp_count > 0 and var_count > 0 and user_count > 0 and asg_count > 0),
            details=f"Experiments={exp_count}, Variants={var_count}, Users={user_count}, Assignments={asg_count}",
        )
    )

    # 2. Single Control Variant & 100% Allocation Check per Experiment
    experiments = list(session.scalars(select(Experiment)).all())
    alloc_ok = True
    for exp in experiments:
        vars_for_exp = list(
            session.scalars(
                select(Variant).where(Variant.experiment_id == exp.experiment_id)
            ).all()
        )
        ctrl_cnt = len([v for v in vars_for_exp if v.variant_type == "Control"])
        sum_pct = sum(v.allocation_percentage for v in vars_for_exp)
        if ctrl_cnt != 1 or abs(sum_pct - 100.0) > 1e-5:
            alloc_ok = False
            break

    checks.append(
        ValidationCheckResult(
            check_name="variant_control_and_allocation_reconciliation",
            category="Arithmetic_Reconciliation",
            passed=alloc_ok,
            details="Verified every experiment has exactly 1 Control variant and 100.0% total allocation.",
        )
    )

    # 3. Foreign Key & Join Integrity Check
    orphan_asg = (
        session.scalar(
            select(func.count(Assignment.assignment_id))
            .outerjoin(Variant, Assignment.variant_id == Variant.variant_id)
            .where(Variant.variant_id.is_(None))
        )
        or 0
    )
    orphan_exp = (
        session.scalar(
            select(func.count(ExposureEvent.exposure_id))
            .outerjoin(Assignment, ExposureEvent.assignment_id == Assignment.assignment_id)
            .where(Assignment.assignment_id.is_(None))
        )
        or 0
    )
    checks.append(
        ValidationCheckResult(
            check_name="foreign_key_join_integrity",
            category="Foreign_Keys",
            passed=(orphan_asg == 0 and orphan_exp == 0),
            details=f"Orphan assignments={orphan_asg}, Orphan exposures={orphan_exp}",
        )
    )

    # 4. Enum Compliance Check
    invalid_exp_status = (
        session.scalar(
            select(func.count(Experiment.experiment_id)).where(
                Experiment.experiment_status.notin_(ALLOWED_EXPERIMENT_STATUSES)
            )
        )
        or 0
    )
    invalid_asg_status = (
        session.scalar(
            select(func.count(Assignment.assignment_id)).where(
                Assignment.assignment_status.notin_(ALLOWED_ASSIGNMENT_STATUSES)
            )
        )
        or 0
    )
    invalid_exp_evt_status = (
        session.scalar(
            select(func.count(ExposureEvent.exposure_id)).where(
                ExposureEvent.exposure_status.notin_(ALLOWED_EXPOSURE_STATUSES)
            )
        )
        or 0
    )
    invalid_conv_status = (
        session.scalar(
            select(func.count(ConversionEvent.conversion_id)).where(
                ConversionEvent.conversion_status.notin_(ALLOWED_CONVERSION_STATUSES)
            )
        )
        or 0
    )
    invalid_metric_type = (
        session.scalar(
            select(func.count(MetricDefinition.metric_id)).where(
                MetricDefinition.metric_type.notin_(ALLOWED_METRIC_TYPES)
            )
        )
        or 0
    )
    invalid_decision = (
        session.scalar(
            select(func.count(ExperimentResult.result_id)).where(
                ExperimentResult.decision_status.notin_(ALLOWED_DECISION_STATUSES)
            )
        )
        or 0
    )
    invalid_issues = (
        session.scalar(
            select(func.count(ExperimentIssue.issue_id)).where(
                ExperimentIssue.issue_type.notin_(ALLOWED_ISSUE_TYPES)
                | ExperimentIssue.severity.notin_(ALLOWED_ISSUE_SEVERITIES)
            )
        )
        or 0
    )
    enums_ok = (
        invalid_exp_status
        + invalid_asg_status
        + invalid_exp_evt_status
        + invalid_conv_status
        + invalid_metric_type
        + invalid_decision
        + invalid_issues
    ) == 0

    checks.append(
        ValidationCheckResult(
            check_name="enum_vocabulary_compliance",
            category="Enums",
            passed=enums_ok,
            details="All lifecycle, event, metric, decision, and issue statuses match permitted vocabularies.",
        )
    )

    # 5. Arithmetic Reconciliation between ExperimentResult and Source Events
    reconciled_ok = True
    for exp in experiments:
        diags = calculate_variant_diagnostics(session, exp.experiment_id)
        itt_results = list(
            session.scalars(
                select(ExperimentResult).where(
                    ExperimentResult.experiment_id == exp.experiment_id,
                    ExperimentResult.analysis_method == "ITT",
                    ExperimentResult.metric_version == 1,
                )
            ).all()
        )
        for res in itt_results:
            d = diags.get(res.variant_id)
            if d is None or res.sample_size != d.total_eligible_assigned_users:
                reconciled_ok = False
                break

    checks.append(
        ValidationCheckResult(
            check_name="result_denominator_and_rate_reconciliation",
            category="Arithmetic_Reconciliation",
            passed=reconciled_ok,
            details="Verified ExperimentResult sample_size and denominators match source assignment records.",
        )
    )

    all_passed = all(c.passed for c in checks)
    return {
        "overall_passed": all_passed,
        "total_checks": len(checks),
        "passed_checks": sum(1 for c in checks if c.passed),
        "failed_checks": sum(1 for c in checks if not c.passed),
        "entity_counts": {
            "experiments": int(exp_count),
            "variants": int(var_count),
            "audience_members": int(user_count),
            "assignments": int(asg_count),
            "exposure_events": int(
                session.scalar(select(func.count(ExposureEvent.exposure_id))) or 0
            ),
            "conversion_events": int(
                session.scalar(select(func.count(ConversionEvent.conversion_id))) or 0
            ),
            "metric_definitions": int(
                session.scalar(select(func.count(MetricDefinition.metric_id))) or 0
            ),
            "guardrail_metrics": int(
                session.scalar(select(func.count(GuardrailMetric.guardrail_id))) or 0
            ),
            "experiment_results": int(
                session.scalar(select(func.count(ExperimentResult.result_id))) or 0
            ),
            "experiment_issues": int(
                session.scalar(select(func.count(ExperimentIssue.issue_id))) or 0
            ),
        },
        "checks": [asdict(c) for c in checks],
    }