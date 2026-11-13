"""Step 10 & Section 10: Statistical inference engine (Pooled z-test, Newcombe-Wilson 95% CI, Welch t-test, and 8-Priority Decision Engine)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np
from scipy.stats import norm, t as student_t, ttest_ind
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import (
    Experiment,
    ExperimentIssue,
    ExperimentResult,
    MetricDefinition,
    Variant,
)
from services.experiment_service import get_control_variant
from services.guardrails import evaluate_guardrails_for_variant
from services.metrics import (
    VariantMetricValue,
    calculate_metric_for_variants,
    get_latest_metric_version,
    resolve_metric_version_at_timestamp,
)
from services.randomization import validate_randomization_srm


@dataclass(frozen=True)
class TwoGroupStatisticalComparison:
    """Statistical comparison between Treatment and Control."""

    control_value: float
    treatment_value: float
    treatment_effect: float
    relative_lift: Optional[float]
    standard_error: float
    confidence_interval_lower: float
    confidence_interval_upper: float
    p_value: float
    statistical_significance: int


def wilson_score_interval(
    successes: float, total: float, alpha: float = 0.05
) -> tuple[float, float]:
    """Compute single-proportion Wilson score confidence interval (l, u)."""
    if total <= 0:
        return 0.0, 0.0
    p_hat = float(np.clip(successes / total, 0.0, 1.0))
    z = float(norm.ppf(1.0 - alpha / 2.0))
    z2 = z * z
    denom = 1.0 + z2 / total
    center = (p_hat + z2 / (2.0 * total)) / denom
    half_width = (
        z
        * math.sqrt((p_hat * (1.0 - p_hat) / total) + (z2 / (4.0 * total * total)))
        / denom
    )
    lower = 0.0 if successes <= 0 or (center - half_width) < 1e-12 else max(0.0, center - half_width)
    upper = 1.0 if successes >= total or (center + half_width) > 1.0 - 1e-12 else min(1.0, center + half_width)
    return lower, upper


def compare_two_proportions(
    x_control: float,
    n_control: float,
    x_treatment: float,
    n_treatment: float,
    alpha: float = 0.05,
) -> TwoGroupStatisticalComparison:
    """Pooled two-proportion z-test for p-value + Newcombe-Wilson score interval for 95% CI."""
    if n_control <= 0 or n_treatment <= 0:
        return TwoGroupStatisticalComparison(
            control_value=0.0,
            treatment_value=0.0,
            treatment_effect=0.0,
            relative_lift=None,
            standard_error=0.0,
            confidence_interval_lower=0.0,
            confidence_interval_upper=0.0,
            p_value=1.0,
            statistical_significance=0,
        )

    p_c = float(np.clip(x_control / n_control, 0.0, 1.0))
    p_t = float(np.clip(x_treatment / n_treatment, 0.0, 1.0))
    diff = p_t - p_c
    rel_lift = ((p_t - p_c) / p_c) if p_c > 0.0 else None

    # Unpooled SE for descriptive reporting
    se_unpooled = math.sqrt(
        max(0.0, (p_c * (1.0 - p_c) / n_control) + (p_t * (1.0 - p_t) / n_treatment))
    )

    # Pooled SE for two-sided null hypothesis z-test (H0: p_T = p_C)
    p_pool = (x_control + x_treatment) / (n_control + n_treatment)
    se_pool = math.sqrt(
        max(0.0, p_pool * (1.0 - p_pool) * (1.0 / n_control + 1.0 / n_treatment))
    )
    if se_pool > 0.0:
        z_stat = diff / se_pool
        p_val = float(2.0 * norm.sf(abs(z_stat)))
    else:
        p_val = 1.0

    p_val = float(np.clip(p_val, 0.0, 1.0))
    sig = 1 if p_val < alpha else 0

    # Newcombe Method 10 (hybrid Wilson score interval for difference of two proportions)
    l_c, u_c = wilson_score_interval(x_control, n_control, alpha=alpha)
    l_t, u_t = wilson_score_interval(x_treatment, n_treatment, alpha=alpha)

    ci_lower = diff - math.sqrt(max(0.0, (p_t - l_t) ** 2 + (u_c - p_c) ** 2))
    ci_upper = diff + math.sqrt(max(0.0, (u_t - p_t) ** 2 + (p_c - l_c) ** 2))

    # Guarantee numerical ordering ci_lower <= diff <= ci_upper
    ci_lower = min(ci_lower, diff)
    ci_upper = max(ci_upper, diff)

    return TwoGroupStatisticalComparison(
        control_value=round(p_c, 8),
        treatment_value=round(p_t, 8),
        treatment_effect=round(diff, 8),
        relative_lift=round(rel_lift, 8) if rel_lift is not None else None,
        standard_error=round(se_unpooled, 8),
        confidence_interval_lower=round(ci_lower, 8),
        confidence_interval_upper=round(ci_upper, 8),
        p_value=round(p_val, 10),
        statistical_significance=sig,
    )


def compare_continuous_means(
    control_values: Sequence[float],
    treatment_values: Sequence[float],
    alpha: float = 0.05,
) -> TwoGroupStatisticalComparison:
    """Welch's two-sample t-test and Welch-Satterthwaite 95% confidence interval for continuous metrics."""
    n_c = len(control_values)
    n_t = len(treatment_values)
    if n_c < 2 or n_t < 2:
        return TwoGroupStatisticalComparison(
            control_value=0.0,
            treatment_value=0.0,
            treatment_effect=0.0,
            relative_lift=None,
            standard_error=0.0,
            confidence_interval_lower=0.0,
            confidence_interval_upper=0.0,
            p_value=1.0,
            statistical_significance=0,
        )

    arr_c = np.asarray(control_values, dtype=np.float64)
    arr_t = np.asarray(treatment_values, dtype=np.float64)
    mean_c = float(np.mean(arr_c))
    mean_t = float(np.mean(arr_t))
    diff = mean_t - mean_c
    rel_lift = (diff / mean_c) if mean_c > 0.0 else None

    var_c = float(np.var(arr_c, ddof=1))
    var_t = float(np.var(arr_t, ddof=1))
    se = math.sqrt(max(0.0, (var_c / n_c) + (var_t / n_t)))

    if se > 0.0:
        t_res = ttest_ind(arr_t, arr_c, equal_var=False)
        p_val = float(np.clip(t_res.pvalue, 0.0, 1.0))
        df_num = (var_c / n_c + var_t / n_t) ** 2
        df_den = ((var_c / n_c) ** 2 / (n_c - 1)) + ((var_t / n_t) ** 2 / (n_t - 1))
        df = df_num / df_den if df_den > 0 else float(n_c + n_t - 2)
        t_crit = float(student_t.ppf(1.0 - alpha / 2.0, df))
        ci_lower = diff - t_crit * se
        ci_upper = diff + t_crit * se
    else:
        p_val = 1.0
        ci_lower = diff
        ci_upper = diff

    sig = 1 if p_val < alpha else 0
    return TwoGroupStatisticalComparison(
        control_value=round(mean_c, 8),
        treatment_value=round(mean_t, 8),
        treatment_effect=round(diff, 8),
        relative_lift=round(rel_lift, 8) if rel_lift is not None else None,
        standard_error=round(se, 8),
        confidence_interval_lower=round(min(ci_lower, diff), 8),
        confidence_interval_upper=round(max(ci_upper, diff), 8),
        p_value=round(p_val, 10),
        statistical_significance=sig,
    )


def resolve_decision_status(
    is_control: bool,
    has_data_quality_or_srm_hold: bool,
    has_metric_version_mismatch: bool,
    guardrail_status: str,
    p_value: Optional[float],
    significance_level: float,
    treatment_effect: Optional[float],
    minimum_detectable_effect: float,
) -> str:
    """Evaluate the strict 8-priority launch decision precedence table."""
    # Priority 0: Control Baseline Row
    if is_control:
        return "CONTROL_BASELINE"

    # Priority 1: Data Quality & SRM Gate
    if has_data_quality_or_srm_hold:
        return "INVALID_DATA_HOLD"

    # Priority 2: Metric Version Currency Gate
    if has_metric_version_mismatch:
        return "RECALCULATION_REQUIRED"

    # Priority 3: Critical Guardrail Breach Gate
    if guardrail_status == "FAILED":
        return "DO_NOT_LAUNCH_GUARDRAIL_BREACH"

    # Priority 4: Guardrail Data Sufficiency Gate
    if guardrail_status == "INSUFFICIENT_DATA":
        return "INSUFFICIENT_GUARDRAIL_DATA"

    # Priority 5: Statistical Significance & Positive Direction Gate
    if (
        p_value is None
        or treatment_effect is None
        or p_value >= significance_level
        or treatment_effect <= 0.0
    ):
        return "DO_NOT_LAUNCH_NO_SIGNIFICANT_LIFT"

    # Priority 6: Practical Significance (MDE) Gate
    if treatment_effect < minimum_detectable_effect:
        return "DO_NOT_LAUNCH_BELOW_MDE"

    # Priority 7: Guardrail Warning Hold Gate
    if guardrail_status == "WARNING":
        return "HOLD_FOR_GUARDRAIL_REVIEW"

    # Priority 8: Unqualified Launch Approval
    return "LAUNCH_TREATMENT"


def run_experiment_analysis(
    session: Session,
    experiment_id: str,
    analysis_run_id: Optional[str] = None,
    analysis_timestamp: str = "2026-01-20T00:00:00Z",
    analysis_methods: Sequence[str] = ("ITT", "EXPOSED_SECONDARY"),
) -> List[ExperimentResult]:
    """Execute Step 10: Compute and append immutable ExperimentResult rows for an experiment."""
    experiment = session.get(Experiment, experiment_id)
    if experiment is None:
        raise ValueError(f"Experiment not found: {experiment_id}")

    # Determine run sequence ID if not explicitly passed
    if analysis_run_id is None:
        existing_runs = len(
            set(
                session.scalars(
                    select(ExperimentResult.analysis_run_id).where(
                        ExperimentResult.experiment_id == experiment_id
                    )
                ).all()
            )
        )
        analysis_run_id = f"RUN-{experiment_id}-{existing_runs + 1:03d}"

    # Resolve primary metric version effective at analysis_timestamp
    metric_def = resolve_metric_version_at_timestamp(
        session,
        experiment_id=experiment_id,
        metric_code=experiment.primary_metric_code,
        analysis_timestamp=analysis_timestamp,
    )

    control_variant = get_control_variant(session, experiment_id)
    variants = list(
        session.scalars(
            select(Variant)
            .where(Variant.experiment_id == experiment_id)
            .order_by(Variant.variant_id.asc())
        ).all()
    )

    # Check SRM status & existing critical data quality issues as of analysis run
    srm_res = validate_randomization_srm(session, experiment_id, record_issue=False)
    critical_issues = list(
        session.scalars(
            select(ExperimentIssue).where(
                ExperimentIssue.experiment_id == experiment_id,
                ExperimentIssue.issue_type.in_(
                    (
                        "DUPLICATE_ASSIGNMENT",
                        "EXPOSURE_BEFORE_ASSIGNMENT",
                        "OUTCOME_WINDOW_VIOLATION",
                        "SRM_DETECTED",
                    )
                ),
                ExperimentIssue.detected_at <= analysis_timestamp,
            )
        ).all()
    )
    has_data_hold = srm_res.srm_detected or len(critical_issues) > 0

    created_results: List[ExperimentResult] = []

    for method in analysis_methods:
        var_metrics: Dict[str, VariantMetricValue] = calculate_metric_for_variants(
            session, experiment_id, metric_def, analysis_method=method
        )
        ctrl_m = var_metrics[control_variant.variant_id]

        for v in variants:
            vm = var_metrics[v.variant_id]
            res_id = (
                f"RES-{analysis_run_id}-{v.variant_id}-"
                f"{metric_def.metric_code}-V{metric_def.metric_version}-{method}"
            )

            if v.variant_id == control_variant.variant_id:
                result_row = ExperimentResult(
                    result_id=res_id,
                    analysis_run_id=analysis_run_id,
                    experiment_id=experiment_id,
                    variant_id=v.variant_id,
                    control_variant_id=control_variant.variant_id,
                    control_variant_type="Control",
                    metric_id=metric_def.metric_id,
                    metric_version=metric_def.metric_version,
                    analysis_method=method,
                    sample_size=vm.sample_size,
                    numerator=vm.numerator,
                    denominator=vm.denominator,
                    metric_value=vm.metric_value,
                    treatment_effect=None,
                    relative_lift=None,
                    standard_error=None,
                    confidence_interval_lower=None,
                    confidence_interval_upper=None,
                    p_value=None,
                    statistical_significance=None,
                    guardrail_status="NOT_APPLICABLE",
                    decision_status="CONTROL_BASELINE",
                    analysis_timestamp=analysis_timestamp,
                )
                created_results.append(result_row)
            else:
                if metric_def.metric_type == "Primary_Continuous":
                    comp = compare_continuous_means(
                        ctrl_m.user_level_values or [],
                        vm.user_level_values or [],
                        alpha=experiment.significance_level,
                    )
                else:
                    comp = compare_two_proportions(
                        x_control=ctrl_m.numerator,
                        n_control=ctrl_m.denominator,
                        x_treatment=vm.numerator,
                        n_treatment=vm.denominator,
                        alpha=experiment.significance_level,
                    )

                grd_status, _ = evaluate_guardrails_for_variant(
                    session, experiment_id, v.variant_id
                )

                decision = resolve_decision_status(
                    is_control=False,
                    has_data_quality_or_srm_hold=has_data_hold,
                    has_metric_version_mismatch=False,
                    guardrail_status=grd_status,
                    p_value=comp.p_value,
                    significance_level=experiment.significance_level,
                    treatment_effect=comp.treatment_effect,
                    minimum_detectable_effect=experiment.minimum_detectable_effect,
                )

                result_row = ExperimentResult(
                    result_id=res_id,
                    analysis_run_id=analysis_run_id,
                    experiment_id=experiment_id,
                    variant_id=v.variant_id,
                    control_variant_id=control_variant.variant_id,
                    control_variant_type="Control",
                    metric_id=metric_def.metric_id,
                    metric_version=metric_def.metric_version,
                    analysis_method=method,
                    sample_size=vm.sample_size,
                    numerator=vm.numerator,
                    denominator=vm.denominator,
                    metric_value=vm.metric_value,
                    treatment_effect=comp.treatment_effect,
                    relative_lift=comp.relative_lift,
                    standard_error=comp.standard_error,
                    confidence_interval_lower=comp.confidence_interval_lower,
                    confidence_interval_upper=comp.confidence_interval_upper,
                    p_value=comp.p_value,
                    statistical_significance=comp.statistical_significance,
                    guardrail_status=grd_status,
                    decision_status=decision,
                    analysis_timestamp=analysis_timestamp,
                )
                created_results.append(result_row)

    session.add_all(created_results)
    session.flush()
    return created_results


def evaluate_current_launch_decision(
    session: Session, experiment_id: str
) -> Dict[str, str]:
    """Evaluate current launch readiness per variant without mutating historical ExperimentResult rows."""
    experiment = session.get(Experiment, experiment_id)
    if experiment is None:
        raise ValueError(f"Experiment not found: {experiment_id}")

    latest_metric = get_latest_metric_version(
        session, experiment_id, experiment.primary_metric_code
    )
    srm_res = validate_randomization_srm(session, experiment_id, record_issue=False)
    open_critical_issues = list(
        session.scalars(
            select(ExperimentIssue).where(
                ExperimentIssue.experiment_id == experiment_id,
                ExperimentIssue.issue_type.in_(
                    (
                        "DUPLICATE_ASSIGNMENT",
                        "EXPOSURE_BEFORE_ASSIGNMENT",
                        "OUTCOME_WINDOW_VIOLATION",
                        "SRM_DETECTED",
                    )
                ),
                ExperimentIssue.resolution_status == "Open",
            )
        ).all()
    )
    has_data_hold = srm_res.srm_detected or len(open_critical_issues) > 0

    # Get latest ITT results
    latest_run_id = session.scalar(
        select(ExperimentResult.analysis_run_id)
        .where(
            ExperimentResult.experiment_id == experiment_id,
            ExperimentResult.analysis_method == "ITT",
        )
        .order_by(
            ExperimentResult.analysis_timestamp.desc(),
            ExperimentResult.analysis_run_id.desc(),
        )
        .limit(1)
    )
    if latest_run_id is None:
        return {}

    run_results = list(
        session.scalars(
            select(ExperimentResult).where(
                ExperimentResult.experiment_id == experiment_id,
                ExperimentResult.analysis_run_id == latest_run_id,
                ExperimentResult.analysis_method == "ITT",
            )
        ).all()
    )

    decisions: Dict[str, str] = {}
    for res in run_results:
        is_ctrl = res.variant_id == res.control_variant_id
        version_mismatch = latest_metric.metric_version > res.metric_version
        decisions[res.variant_id] = resolve_decision_status(
            is_control=is_ctrl,
            has_data_quality_or_srm_hold=has_data_hold,
            has_metric_version_mismatch=version_mismatch,
            guardrail_status=res.guardrail_status,
            p_value=res.p_value,
            significance_level=experiment.significance_level,
            treatment_effect=res.treatment_effect,
            minimum_detectable_effect=experiment.minimum_detectable_effect,
        )

    return decisions