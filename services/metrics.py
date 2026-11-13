"""Step 8 & Section 9: Versioned metric resolution and variant-level metric calculation engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from database.models import (
    Assignment,
    AudienceMember,
    ConversionEvent,
    Experiment,
    ExposureEvent,
    MetricDefinition,
    Variant,
)


@dataclass(frozen=True)
class VariantDiagnosticCounts:
    """Complete operational and metric breakdown for a single variant."""

    experiment_id: str
    variant_id: str
    variant_name: str
    variant_type: str
    total_assigned_users: int
    total_eligible_assigned_users: int
    total_exposed_users: int
    total_conversions: int
    conversion_rate_itt: float
    conversion_rate_exposed: float
    total_conversion_value: float
    mean_conversion_value_itt: float
    missing_telemetry_count: int
    noncompliance_count: int
    delayed_conversion_count: int
    outside_window_conversion_count: int
    refund_users_count: int
    payment_failure_users_count: int
    complaint_users_count: int


@dataclass(frozen=True)
class VariantMetricValue:
    """Calculated numerator, denominator, and metric_value for a specific MetricDefinition."""

    experiment_id: str
    variant_id: str
    metric_id: str
    metric_code: str
    metric_version: int
    analysis_method: str
    sample_size: int
    numerator: float
    denominator: float
    metric_value: float
    user_level_values: Optional[List[float]] = None


def resolve_metric_version_at_timestamp(
    session: Session,
    experiment_id: str,
    metric_code: str,
    analysis_timestamp: str,
) -> MetricDefinition:
    """Resolve the active MetricDefinition at analysis_timestamp using LEAD(effective_from)."""
    query = text(
        """
        WITH version_windows AS (
            SELECT
                metric_id,
                experiment_id,
                metric_code,
                metric_version,
                effective_from,
                LEAD(effective_from) OVER (
                    PARTITION BY experiment_id, metric_code
                    ORDER BY metric_version ASC
                ) AS derived_effective_to
            FROM metric_definitions
            WHERE experiment_id = :exp_id
              AND metric_code = :code
        )
        SELECT metric_id
        FROM version_windows
        WHERE effective_from <= :ts
          AND (derived_effective_to IS NULL OR :ts < derived_effective_to)
        ORDER BY metric_version DESC
        LIMIT 1
        """
    )
    row = session.execute(
        query,
        {"exp_id": experiment_id, "code": metric_code, "ts": analysis_timestamp},
    ).fetchone()

    if row is None:
        # Fallback to version 1 if analysis_timestamp precedes V1 effective_from
        fallback = session.scalar(
            select(MetricDefinition)
            .where(
                MetricDefinition.experiment_id == experiment_id,
                MetricDefinition.metric_code == metric_code,
            )
            .order_by(MetricDefinition.metric_version.asc())
            .limit(1)
        )
        if fallback is None:
            raise ValueError(
                f"No MetricDefinition found for ({experiment_id}, {metric_code})."
            )
        return fallback

    metric_def = session.get(MetricDefinition, str(row[0]))
    if metric_def is None:
        raise ValueError(f"MetricDefinition record missing for ID {row[0]}.")
    return metric_def


def get_latest_metric_version(
    session: Session, experiment_id: str, metric_code: str
) -> MetricDefinition:
    """Return the latest appended MetricDefinition version for (experiment_id, metric_code)."""
    metric_def = session.scalar(
        select(MetricDefinition)
        .where(
            MetricDefinition.experiment_id == experiment_id,
            MetricDefinition.metric_code == metric_code,
        )
        .order_by(MetricDefinition.metric_version.desc())
        .limit(1)
    )
    if metric_def is None:
        raise ValueError(
            f"No MetricDefinition found for ({experiment_id}, {metric_code})."
        )
    return metric_def


def calculate_variant_diagnostics(
    session: Session, experiment_id: str
) -> Dict[str, VariantDiagnosticCounts]:
    """Compute all 10 required variant operational and telemetry counts from source records."""
    experiment = session.get(Experiment, experiment_id)
    if experiment is None:
        raise ValueError(f"Experiment not found: {experiment_id}")

    variants = list(
        session.scalars(
            select(Variant)
            .where(Variant.experiment_id == experiment_id)
            .order_by(Variant.variant_id.asc())
        ).all()
    )

    assignments = list(
        session.scalars(
            select(Assignment).where(
                Assignment.experiment_id == experiment_id,
                Assignment.assignment_status == "Assigned",
            )
        ).all()
    )
    eligible_user_ids: Set[str] = set(
        session.scalars(
            select(AudienceMember.user_id)
            .join(Assignment, Assignment.user_id == AudienceMember.user_id)
            .where(
                Assignment.experiment_id == experiment_id,
                AudienceMember.eligibility_status == "Eligible",
            )
        ).all()
    )

    exposures = list(
        session.scalars(
            select(ExposureEvent).where(ExposureEvent.experiment_id == experiment_id)
        ).all()
    )
    conversions = list(
        session.scalars(
            select(ConversionEvent).where(
                ConversionEvent.experiment_id == experiment_id
            )
        ).all()
    )

    asg_by_id = {a.assignment_id: a for a in assignments}
    asg_by_user: Dict[str, Assignment] = {a.user_id: a for a in assignments}
    window_delta = timedelta(days=experiment.conversion_window_days)

    # Index exposures by variant
    exposed_users_by_var: Dict[str, Set[str]] = {v.variant_id: set() for v in variants}
    missing_tel_by_var: Dict[str, int] = {v.variant_id: 0 for v in variants}
    noncompliance_by_var: Dict[str, int] = {v.variant_id: 0 for v in variants}

    for exp_evt in exposures:
        vid = exp_evt.variant_id
        if vid not in exposed_users_by_var:
            continue
        parent_asg = asg_by_id.get(exp_evt.assignment_id)
        is_valid_order = (
            parent_asg is not None
            and exp_evt.exposure_timestamp >= parent_asg.assigned_at
        )
        if exp_evt.exposure_status == "Exposed" and is_valid_order:
            exposed_users_by_var[vid].add(exp_evt.user_id)
        if exp_evt.telemetry_status == "Missing":
            missing_tel_by_var[vid] += 1
        if exp_evt.exposure_status == "Noncompliant":
            noncompliance_by_var[vid] += 1

    # Index conversions by variant within valid conversion window
    converted_users_by_var: Dict[str, Set[str]] = {
        v.variant_id: set() for v in variants
    }
    conv_value_by_var: Dict[str, float] = {v.variant_id: 0.0 for v in variants}
    delayed_conv_by_var: Dict[str, int] = {v.variant_id: 0 for v in variants}
    outside_win_by_var: Dict[str, int] = {v.variant_id: 0 for v in variants}
    refund_users_by_var: Dict[str, Set[str]] = {v.variant_id: set() for v in variants}
    payfail_users_by_var: Dict[str, Set[str]] = {v.variant_id: set() for v in variants}
    complaint_users_by_var: Dict[str, Set[str]] = {
        v.variant_id: set() for v in variants
    }

    for conv in conversions:
        parent_asg = (
            asg_by_id.get(conv.assignment_id)
            if conv.assignment_id
            else asg_by_user.get(conv.user_id)
        )
        if parent_asg is None:
            continue
        vid = parent_asg.variant_id
        if vid not in converted_users_by_var:
            continue

        asg_dt = datetime.fromisoformat(parent_asg.assigned_at.replace("Z", "+00:00"))
        conv_dt = datetime.fromisoformat(
            conv.conversion_timestamp.replace("Z", "+00:00")
        )
        in_window = (
            asg_dt <= conv_dt <= (asg_dt + window_delta)
            and conv.conversion_status in ("Valid", "Delayed_In_Window")
        )

        if conv.conversion_status == "Delayed_In_Window":
            delayed_conv_by_var[vid] += 1
        if conv.conversion_status == "Outside_Window" or not (
            asg_dt <= conv_dt <= (asg_dt + window_delta)
        ):
            outside_win_by_var[vid] += 1
            continue

        if not in_window:
            continue

        if conv.conversion_type == "Purchase":
            converted_users_by_var[vid].add(conv.user_id)
            conv_value_by_var[vid] += float(conv.conversion_value)
        elif conv.conversion_type == "Refund":
            refund_users_by_var[vid].add(conv.user_id)
        elif conv.conversion_type == "Payment_Failure":
            payfail_users_by_var[vid].add(conv.user_id)
        elif conv.conversion_type == "Complaint":
            complaint_users_by_var[vid].add(conv.user_id)

    results: Dict[str, VariantDiagnosticCounts] = {}
    for v in variants:
        vid = v.variant_id
        var_asgs = [a for a in assignments if a.variant_id == vid]
        total_asg = len(var_asgs)
        elig_asg = len([a for a in var_asgs if a.user_id in eligible_user_ids])
        exposed_cnt = len(exposed_users_by_var[vid])
        conv_cnt = len(converted_users_by_var[vid])
        exposed_conv_cnt = len(
            converted_users_by_var[vid].intersection(exposed_users_by_var[vid])
        )
        tot_val = round(conv_value_by_var[vid], 4)

        rate_itt = (conv_cnt / elig_asg) if elig_asg > 0 else 0.0
        rate_exp = (exposed_conv_cnt / exposed_cnt) if exposed_cnt > 0 else 0.0
        mean_val_itt = (tot_val / elig_asg) if elig_asg > 0 else 0.0

        results[vid] = VariantDiagnosticCounts(
            experiment_id=experiment_id,
            variant_id=vid,
            variant_name=v.variant_name,
            variant_type=v.variant_type,
            total_assigned_users=total_asg,
            total_eligible_assigned_users=elig_asg,
            total_exposed_users=exposed_cnt,
            total_conversions=conv_cnt,
            conversion_rate_itt=round(rate_itt, 8),
            conversion_rate_exposed=round(rate_exp, 8),
            total_conversion_value=tot_val,
            mean_conversion_value_itt=round(mean_val_itt, 8),
            missing_telemetry_count=missing_tel_by_var[vid],
            noncompliance_count=noncompliance_by_var[vid],
            delayed_conversion_count=delayed_conv_by_var[vid],
            outside_window_conversion_count=outside_win_by_var[vid],
            refund_users_count=len(refund_users_by_var[vid]),
            payment_failure_users_count=len(payfail_users_by_var[vid]),
            complaint_users_count=len(complaint_users_by_var[vid]),
        )

    return results


def calculate_metric_for_variants(
    session: Session,
    experiment_id: str,
    metric_def: MetricDefinition,
    analysis_method: str = "ITT",
) -> Dict[str, VariantMetricValue]:
    """Calculate exact numerator, denominator, and metric_value per variant for a MetricDefinition."""
    diagnostics = calculate_variant_diagnostics(session, experiment_id)
    experiment = session.get(Experiment, experiment_id)
    if experiment is None:
        raise ValueError(f"Experiment not found: {experiment_id}")

    # For continuous metrics, collect user-level conversion values per variant for Welch's t-test
    user_values_by_var: Dict[str, List[float]] = {}
    if metric_def.metric_type == "Primary_Continuous":
        assignments = list(
            session.scalars(
                select(Assignment).where(
                    Assignment.experiment_id == experiment_id,
                    Assignment.assignment_status == "Assigned",
                )
            ).all()
        )
        conversions = list(
            session.scalars(
                select(ConversionEvent).where(
                    ConversionEvent.experiment_id == experiment_id,
                    ConversionEvent.conversion_type == "Purchase",
                )
            ).all()
        )
        window_delta = timedelta(days=experiment.conversion_window_days)
        asg_by_user = {a.user_id: a for a in assignments}
        user_spend: Dict[str, float] = {a.user_id: 0.0 for a in assignments}

        for conv in conversions:
            parent_asg = asg_by_user.get(conv.user_id)
            if parent_asg is None:
                continue
            asg_dt = datetime.fromisoformat(
                parent_asg.assigned_at.replace("Z", "+00:00")
            )
            conv_dt = datetime.fromisoformat(
                conv.conversion_timestamp.replace("Z", "+00:00")
            )
            if (
                asg_dt <= conv_dt <= (asg_dt + window_delta)
                and conv.conversion_status in ("Valid", "Delayed_In_Window")
            ):
                user_spend[conv.user_id] += float(conv.conversion_value)

        for vid in diagnostics:
            user_values_by_var[vid] = [
                user_spend[a.user_id] for a in assignments if a.variant_id == vid
            ]

    output: Dict[str, VariantMetricValue] = {}
    use_exposed = (
        analysis_method == "EXPOSED_SECONDARY"
        or metric_def.calculation_method == "Exposed_Proportion"
    )

    for vid, diag in diagnostics.items():
        denom = float(
            diag.total_exposed_users
            if use_exposed
            else diag.total_eligible_assigned_users
        )
        sample_n = int(denom)

        if metric_def.metric_type == "Primary_Continuous":
            num = float(diag.total_conversion_value)
            val = (num / denom) if denom > 0 else 0.0
        elif metric_def.metric_code.endswith("-REFUND"):
            num = float(diag.refund_users_count)
            val = (num / denom) if denom > 0 else 0.0
        elif metric_def.metric_code.endswith("-PAYFAIL"):
            num = float(diag.payment_failure_users_count)
            val = (num / denom) if denom > 0 else 0.0
        elif metric_def.metric_code.endswith("-COMPLAINT"):
            num = float(diag.complaint_users_count)
            val = (num / denom) if denom > 0 else 0.0
        else:
            # Primary_Binary conversion rate
            if use_exposed:
                val = diag.conversion_rate_exposed
                num = round(val * denom, 4)
            else:
                num = float(diag.total_conversions)
                val = (num / denom) if denom > 0 else 0.0

        output[vid] = VariantMetricValue(
            experiment_id=experiment_id,
            variant_id=vid,
            metric_id=metric_def.metric_id,
            metric_code=metric_def.metric_code,
            metric_version=metric_def.metric_version,
            analysis_method=analysis_method,
            sample_size=sample_n,
            numerator=round(num, 6),
            denominator=round(denom, 6),
            metric_value=round(val, 8),
            user_level_values=user_values_by_var.get(vid),
        )

    return output