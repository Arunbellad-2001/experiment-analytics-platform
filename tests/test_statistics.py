"""Automated test suite for Milestone 4: Two-proportion z-test, Newcombe-Wilson CI, and significance consistency."""

from __future__ import annotations

from services.statistics import (
    compare_continuous_means,
    compare_two_proportions,
    resolve_decision_status,
    wilson_score_interval,
)


def test_pooled_z_test_and_newcombe_wilson_ci() -> None:
    """Verify two-proportion hypothesis test and Newcombe-Wilson 95% confidence interval bounds."""
    # Control: 250 / 2500 (10.0%), Treatment: 325 / 2500 (13.0%) -> +3.0 pp lift
    comp = compare_two_proportions(
        x_control=250, n_control=2500, x_treatment=325, n_treatment=2500, alpha=0.05
    )
    assert comp.control_value == 0.10
    assert comp.treatment_value == 0.13
    assert comp.treatment_effect == 0.03
    assert comp.relative_lift == 0.30
    assert comp.p_value < 0.001
    assert comp.statistical_significance == 1
    assert comp.confidence_interval_lower < comp.treatment_effect < comp.confidence_interval_upper
    assert comp.confidence_interval_lower > 0.012

    # Boundary case: zero conversions in control
    zero_comp = compare_two_proportions(
        x_control=0, n_control=100, x_treatment=5, n_treatment=100, alpha=0.05
    )
    assert zero_comp.control_value == 0.0
    assert zero_comp.treatment_value == 0.05
    assert zero_comp.relative_lift is None
    assert zero_comp.confidence_interval_lower <= zero_comp.treatment_effect <= zero_comp.confidence_interval_upper

    l_bound, u_bound = wilson_score_interval(0, 100, alpha=0.05)
    assert l_bound == 0.0
    assert u_bound > 0.0


def test_continuous_welch_t_test() -> None:
    """Verify Welch's two-sample t-test for continuous metrics."""
    ctrl = [10.0, 12.0, 11.0, 9.0, 10.5, 11.5] * 20
    trt = [14.0, 15.0, 13.5, 16.0, 14.5, 15.5] * 20
    comp = compare_continuous_means(ctrl, trt, alpha=0.05)
    assert comp.treatment_effect > 3.0
    assert comp.p_value < 0.0001
    assert comp.statistical_significance == 1
    assert comp.confidence_interval_lower < comp.treatment_effect < comp.confidence_interval_upper


def test_p_value_statistical_significance_consistency() -> None:
    """Verify Priority 5 uses p_value < significance_level and treatment_effect > 0 consistently."""
    # p_value < 0.05 and treatment_effect >= MDE -> LAUNCH_TREATMENT
    status_win = resolve_decision_status(
        is_control=False,
        has_data_quality_or_srm_hold=False,
        has_metric_version_mismatch=False,
        guardrail_status="PASSED",
        p_value=0.012,
        significance_level=0.05,
        treatment_effect=0.025,
        minimum_detectable_effect=0.020,
    )
    assert status_win == "LAUNCH_TREATMENT"

    # p_value >= 0.05 -> DO_NOT_LAUNCH_NO_SIGNIFICANT_LIFT
    status_insig = resolve_decision_status(
        is_control=False,
        has_data_quality_or_srm_hold=False,
        has_metric_version_mismatch=False,
        guardrail_status="PASSED",
        p_value=0.08,
        significance_level=0.05,
        treatment_effect=0.025,
        minimum_detectable_effect=0.020,
    )
    assert status_insig == "DO_NOT_LAUNCH_NO_SIGNIFICANT_LIFT"