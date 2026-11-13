"""Step 13 & Section 12: Blind anomaly detection engine scanning operational tables for all 5 edge cases."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import (
    Assignment,
    ConversionEvent,
    Experiment,
    ExperimentIssue,
    ExperimentResult,
    ExposureEvent,
    MetricDefinition,
)
from services.randomization import validate_randomization_srm


def _record_issue_if_new(
    session: Session,
    experiment_id: str,
    affected_entity: str,
    affected_record_id: str,
    issue_type: str,
    severity: str,
    detected_at: str,
    description: str,
    expected_behavior: str,
    actual_behavior: str,
) -> ExperimentIssue:
    """Idempotently persist a detected ExperimentIssue into experiment_issues."""
    existing = session.scalar(
        select(ExperimentIssue).where(
            ExperimentIssue.experiment_id == experiment_id,
            ExperimentIssue.issue_type == issue_type,
            ExperimentIssue.affected_record_id == affected_record_id,
        )
    )
    if existing is not None:
        return existing

    count = (
        session.scalar(
            select(func.count(ExperimentIssue.issue_id)).where(
                ExperimentIssue.experiment_id == experiment_id
            )
        )
        or 0
    )
    issue_id = f"ISS-{experiment_id}-{int(count) + 1:04d}"
    issue = ExperimentIssue(
        issue_id=issue_id,
        experiment_id=experiment_id,
        affected_entity=affected_entity,
        affected_record_id=affected_record_id,
        issue_type=issue_type,
        severity=severity,
        detected_at=detected_at,
        description=description,
        expected_behavior=expected_behavior,
        actual_behavior=actual_behavior,
        resolution_status="Open",
    )
    session.add(issue)
    session.flush()
    return issue


def detect_all_anomalies(
    session: Session,
    detected_at: str = "2026-01-26T00:00:00Z",
) -> List[ExperimentIssue]:
    """Scan operational tables blindly (without reading ground-truth files) for all 5 negative scenarios."""
    experiments = list(
        session.scalars(
            select(Experiment).order_by(Experiment.experiment_id.asc())
        ).all()
    )

    for exp in experiments:
        exp_id = exp.experiment_id

        # 1. Edge Case 1: User assigned to multiple variants within the same experiment
        dup_user_rows = session.execute(
            select(
                Assignment.user_id,
                func.count(func.distinct(Assignment.variant_id)),
            )
            .where(Assignment.experiment_id == exp_id)
            .group_by(Assignment.user_id)
            .having(func.count(func.distinct(Assignment.variant_id)) > 1)
        ).all()

        for user_id, distinct_var_count in dup_user_rows:
            _record_issue_if_new(
                session=session,
                experiment_id=exp_id,
                affected_entity="assignments",
                affected_record_id=str(user_id),
                issue_type="DUPLICATE_ASSIGNMENT",
                severity="CRITICAL",
                detected_at=detected_at,
                description=(
                    f"User {user_id} is assigned to {distinct_var_count} distinct variants "
                    f"in experiment {exp_id}."
                ),
                expected_behavior="Exactly 1 variant assignment per eligible user per experiment",
                actual_behavior=f"Found {distinct_var_count} distinct variant assignments for {user_id}",
            )

        # 2. Edge Case 2: Exposure occurring before parent assignment timestamp
        early_exposures = session.execute(
            select(
                ExposureEvent.exposure_id,
                ExposureEvent.exposure_timestamp,
                Assignment.assigned_at,
            )
            .join(
                Assignment,
                ExposureEvent.assignment_id == Assignment.assignment_id,
            )
            .where(
                ExposureEvent.experiment_id == exp_id,
                ExposureEvent.exposure_timestamp < Assignment.assigned_at,
            )
            .order_by(ExposureEvent.exposure_id.asc())
        ).all()

        for exp_evt_id, exp_ts, asg_ts in early_exposures:
            _record_issue_if_new(
                session=session,
                experiment_id=exp_id,
                affected_entity="exposure_events",
                affected_record_id=str(exp_evt_id),
                issue_type="EXPOSURE_BEFORE_ASSIGNMENT",
                severity="CRITICAL",
                detected_at=detected_at,
                description=(
                    f"Exposure {exp_evt_id} timestamp ({exp_ts}) precedes parent "
                    f"assignment timestamp ({asg_ts})."
                ),
                expected_behavior="exposure_timestamp >= assigned_at",
                actual_behavior=f"exposure_timestamp ({exp_ts}) < assigned_at ({asg_ts})",
            )

        # 3. Edge Case 3: Conversion outside the configured conversion window
        conversions = list(
            session.scalars(
                select(ConversionEvent)
                .where(ConversionEvent.experiment_id == exp_id)
                .order_by(ConversionEvent.conversion_id.asc())
            ).all()
        )
        asg_by_id = {
            a.assignment_id: a
            for a in session.scalars(
                select(Assignment).where(Assignment.experiment_id == exp_id)
            ).all()
        }
        window_delta = timedelta(days=exp.conversion_window_days)

        for conv in conversions:
            parent_asg = (
                asg_by_id.get(conv.assignment_id) if conv.assignment_id else None
            )
            if parent_asg is None:
                continue
            asg_dt = datetime.fromisoformat(
                parent_asg.assigned_at.replace("Z", "+00:00")
            )
            conv_dt = datetime.fromisoformat(
                conv.conversion_timestamp.replace("Z", "+00:00")
            )
            max_dt = asg_dt + window_delta
            if conv_dt > max_dt or conv_dt < asg_dt:
                _record_issue_if_new(
                    session=session,
                    experiment_id=exp_id,
                    affected_entity="conversion_events",
                    affected_record_id=conv.conversion_id,
                    issue_type="OUTCOME_WINDOW_VIOLATION",
                    severity="CRITICAL",
                    detected_at=detected_at,
                    description=(
                        f"Conversion {conv.conversion_id} occurred at {conv.conversion_timestamp}, "
                        f"outside the {exp.conversion_window_days}-day window from {parent_asg.assigned_at}."
                    ),
                    expected_behavior=(
                        f"conversion_timestamp within [{parent_asg.assigned_at}, "
                        f"{max_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}]"
                    ),
                    actual_behavior=f"conversion_timestamp = {conv.conversion_timestamp}",
                )

        # 4. Edge Case 4: Sample Ratio Mismatch (SRM)
        validate_randomization_srm(
            session=session,
            experiment_id=exp_id,
            record_issue=True,
            detected_at=detected_at,
        )

        # 5. Edge Case 5: Metric definition changed after results were calculated
        latest_metric = session.scalar(
            select(MetricDefinition)
            .where(
                MetricDefinition.experiment_id == exp_id,
                MetricDefinition.metric_code == exp.primary_metric_code,
            )
            .order_by(MetricDefinition.metric_version.desc())
            .limit(1)
        )
        latest_result_ver = session.scalar(
            select(func.max(ExperimentResult.metric_version)).where(
                ExperimentResult.experiment_id == exp_id
            )
        )
        if (
            latest_metric is not None
            and latest_result_ver is not None
            and latest_metric.metric_version > int(latest_result_ver)
        ):
            _record_issue_if_new(
                session=session,
                experiment_id=exp_id,
                affected_entity="metric_definitions",
                affected_record_id=latest_metric.metric_id,
                issue_type="METRIC_VERSION_MISMATCH",
                severity="WARNING",
                detected_at=detected_at,
                description=(
                    f"Primary metric {exp.primary_metric_code} was updated to version "
                    f"{latest_metric.metric_version} ({latest_metric.metric_id}) after "
                    f"results were calculated under version {latest_result_ver}."
                ),
                expected_behavior="Latest ExperimentResult should match latest active MetricDefinition version",
                actual_behavior=(
                    f"Latest result uses version {latest_result_ver}, "
                    f"but version {latest_metric.metric_version} is active"
                ),
            )

    return list(
        session.scalars(
            select(ExperimentIssue).order_by(ExperimentIssue.issue_id.asc())
        ).all()
    )