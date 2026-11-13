"""Step 9 & Section 11: Configurable guardrail evaluation engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from config.settings import MIN_GUARDRAIL_DENOMINATOR
from database.models import GuardrailMetric, MetricDefinition
from services.experiment_service import get_control_variant
from services.metrics import calculate_metric_for_variants


@dataclass(frozen=True)
class GuardrailEvaluationItem:
    """Single guardrail rule evaluation result."""

    guardrail_id: str
    guardrail_name: str
    metric_id: str
    metric_name: str
    metric_version: int
    severity: str
    threshold_type: str
    comparison_direction: str
    control_value: float
    treatment_value: float
    difference: float
    relative_lift: float
    threshold_value: float
    evaluation_status: str
    explanation: str


def evaluate_guardrails_for_variant(
    session: Session,
    experiment_id: str,
    treatment_variant_id: str,
    min_denominator: int = MIN_GUARDRAIL_DENOMINATOR,
) -> Tuple[str, List[GuardrailEvaluationItem]]:
    """Evaluate all configured guardrails for a treatment variant and return aggregate status + details."""
    control_variant = get_control_variant(session, experiment_id)
    guardrail_defs = list(
        session.scalars(
            select(GuardrailMetric)
            .where(GuardrailMetric.experiment_id == experiment_id)
            .order_by(GuardrailMetric.guardrail_id.asc())
        ).all()
    )

    if not guardrail_defs:
        return "PASSED", []

    items: List[GuardrailEvaluationItem] = []

    for grd in guardrail_defs:
        metric_def = session.get(MetricDefinition, grd.metric_id)
        if metric_def is None:
            continue

        var_metrics = calculate_metric_for_variants(
            session, experiment_id, metric_def, analysis_method="ITT"
        )
        ctrl_m = var_metrics.get(control_variant.variant_id)
        trt_m = var_metrics.get(treatment_variant_id)

        if (
            ctrl_m is None
            or trt_m is None
            or ctrl_m.denominator < min_denominator
            or trt_m.denominator < min_denominator
        ):
            items.append(
                GuardrailEvaluationItem(
                    guardrail_id=grd.guardrail_id,
                    guardrail_name=grd.guardrail_name,
                    metric_id=grd.metric_id,
                    metric_name=metric_def.metric_name,
                    metric_version=grd.metric_version,
                    severity=grd.severity,
                    threshold_type=grd.threshold_type,
                    comparison_direction=grd.comparison_direction,
                    control_value=ctrl_m.metric_value if ctrl_m else 0.0,
                    treatment_value=trt_m.metric_value if trt_m else 0.0,
                    difference=0.0,
                    relative_lift=0.0,
                    threshold_value=grd.threshold_value,
                    evaluation_status="INSUFFICIENT_DATA",
                    explanation=(
                        f"Denominator below minimum required sample ({min_denominator}) "
                        "to evaluate guardrail safely."
                    ),
                )
            )
            continue

        c_val = ctrl_m.metric_value
        t_val = trt_m.metric_value
        diff = t_val - c_val
        rel_lift = (diff / c_val) if c_val > 0.0 else 0.0

        if grd.threshold_type == "Absolute_Diff":
            observed_comp = diff
        elif grd.threshold_type == "Relative_Lift":
            observed_comp = rel_lift
        else:  # Max_Rate
            observed_comp = t_val

        if grd.comparison_direction == "MAX_INCREASE":
            breached = observed_comp > grd.threshold_value
        elif grd.comparison_direction == "MIN_DECREASE":
            breached = observed_comp < - abs(grd.threshold_value)
        else:  # ABSOLUTE_CAP
            breached = t_val > grd.threshold_value

        if breached:
            status = "FAILED" if grd.severity == "CRITICAL" else "WARNING"
            explanation = (
                f"{grd.guardrail_name} breached ({grd.severity}): "
                f"Control={c_val:.4f}, Treatment={t_val:.4f}, Diff={diff:+.4f} "
                f"exceeded threshold {grd.threshold_value:+.4f}."
            )
        else:
            status = "PASSED"
            explanation = (
                f"{grd.guardrail_name} within safe bounds: "
                f"Control={c_val:.4f}, Treatment={t_val:.4f}, Diff={diff:+.4f} "
                f"(threshold {grd.threshold_value:+.4f})."
            )

        items.append(
            GuardrailEvaluationItem(
                guardrail_id=grd.guardrail_id,
                guardrail_name=grd.guardrail_name,
                metric_id=grd.metric_id,
                metric_name=metric_def.metric_name,
                metric_version=grd.metric_version,
                severity=grd.severity,
                threshold_type=grd.threshold_type,
                comparison_direction=grd.comparison_direction,
                control_value=round(c_val, 8),
                treatment_value=round(t_val, 8),
                difference=round(diff, 8),
                relative_lift=round(rel_lift, 8),
                threshold_value=grd.threshold_value,
                evaluation_status=status,
                explanation=explanation,
            )
        )

    statuses = {item.evaluation_status for item in items}
    if "FAILED" in statuses:
        aggregate_status = "FAILED"
    elif "INSUFFICIENT_DATA" in statuses:
        aggregate_status = "INSUFFICIENT_DATA"
    elif "WARNING" in statuses:
        aggregate_status = "WARNING"
    else:
        aggregate_status = "PASSED"

    return aggregate_status, items