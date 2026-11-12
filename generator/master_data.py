"""Steps 1 & 2 (plus initial V1 metric and guardrail definitions): Experiment and Variant master data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from sqlalchemy.orm import Session

from config.settings import (
     DEFAULT_RANDOM_SEED,
    DEFAULT_SIGNIFICANCE_LEVEL,
    REFERENCE_EPOCH_ISO,
    DatasetScaleConfig,
)
from database.models import (
    Experiment,
    ExperimentEvent,
    GuardrailMetric,
    MetricDefinition,
    Variant,
)


@dataclass(frozen=True)
class ExperimentBlueprint:
    """Blueprint defining realistic business parameters for each synthetic experiment."""

    index: int
    name: str
    description: str
    hypothesis: str
    primary_metric_suffix: str
    primary_metric_name: str
    primary_metric_type: str
    calculation_method: str
    minimum_detectable_effect: float
    control_allocation_pct: float
    treatment_allocation_pct: float
    conversion_window_days: int
    baseline_conversion_rate: float
    treatment_effect_delta: float
    baseline_mean_value: float
    treatment_value_delta: float
    refund_rate_control: float
    refund_rate_treatment: float
    payment_failure_control: float
    payment_failure_treatment: float
    complaint_rate_control: float
    complaint_rate_treatment: float
    scenario_tag: str


EXPERIMENT_BLUEPRINTS: Tuple[ExperimentBlueprint, ...] = (
    ExperimentBlueprint(
        index=1,
        name="One-Click Express Checkout Flow",
        description="Evaluates streamlined single-page checkout vs standard multi-step checkout.",
        hypothesis="Streamlined checkout increases purchase conversion rate by at least 2.0 percentage points without increasing payment failures.",
        primary_metric_suffix="CONV",
        primary_metric_name="Purchase Conversion Rate",
        primary_metric_type="Primary_Binary",
        calculation_method="ITT_Proportion",
        minimum_detectable_effect=0.02,
        control_allocation_pct=50.0,
        treatment_allocation_pct=50.0,
        conversion_window_days=7,
        baseline_conversion_rate=0.120,
        treatment_effect_delta=0.032,
        baseline_mean_value=65.0,
        treatment_value_delta=2.0,
        refund_rate_control=0.015,
        refund_rate_treatment=0.014,
        payment_failure_control=0.010,
        payment_failure_treatment=0.009,
        complaint_rate_control=0.005,
        complaint_rate_treatment=0.005,
        scenario_tag="CLEAR_WIN_LAUNCH",
    ),
    ExperimentBlueprint(
        index=2,
        name="Dynamic Cart Upsell Carousel",
        description="Introduces AI-ranked cross-sell recommendations inside the shopping cart drawer.",
        hypothesis="Cross-sell carousel increases average order revenue per assigned user by at least $3.00.",
        primary_metric_suffix="REV",
        primary_metric_name="Revenue Per Assigned User",
        primary_metric_type="Primary_Continuous",
        calculation_method="ITT_Mean_Value",
        minimum_detectable_effect=3.00,
        control_allocation_pct=50.0,
        treatment_allocation_pct=50.0,
        conversion_window_days=7,
        baseline_conversion_rate=0.150,
        treatment_effect_delta=0.025,
        baseline_mean_value=72.0,
        treatment_value_delta=24.0,
        refund_rate_control=0.012,
        refund_rate_treatment=0.013,
        payment_failure_control=0.008,
        payment_failure_treatment=0.008,
        complaint_rate_control=0.004,
        complaint_rate_treatment=0.004,
        scenario_tag="CONTINUOUS_REVENUE_WIN",
    ),
    ExperimentBlueprint(
        index=3,
        name="Aggressive Countdown Timer Banner",
        description="Displays high-urgency countdown timer on checkout page to accelerate purchase completion.",
        hypothesis="Urgency banner increases conversion rate by at least 1.5 percentage points.",
        primary_metric_suffix="CONV",
        primary_metric_name="Purchase Conversion Rate",
        primary_metric_type="Primary_Binary",
        calculation_method="ITT_Proportion",
        minimum_detectable_effect=0.015,
        control_allocation_pct=50.0,
        treatment_allocation_pct=50.0,
        conversion_window_days=7,
        baseline_conversion_rate=0.110,
        treatment_effect_delta=0.028,
        baseline_mean_value=58.0,
        treatment_value_delta=0.0,
        refund_rate_control=0.015,
        refund_rate_treatment=0.042,  # Critical guardrail breach (> +1.0 pp increase)
        payment_failure_control=0.010,
        payment_failure_treatment=0.010,
        complaint_rate_control=0.006,
        complaint_rate_treatment=0.022,
        scenario_tag="GUARDRAIL_BREACH_BLOCK",
    ),
    ExperimentBlueprint(
        index=4,
        name="Enterprise Tier Guided Onboarding",
        description="Tests high-touch interactive onboarding wizard with an intentional 80:20 Control/Treatment split.",
        hypothesis="Guided onboarding improves enterprise activation conversion by at least 2.5 percentage points.",
        primary_metric_suffix="CONV",
        primary_metric_name="Activation Conversion Rate",
        primary_metric_type="Primary_Binary",
        calculation_method="ITT_Proportion",
        minimum_detectable_effect=0.025,
        control_allocation_pct=80.0,
        treatment_allocation_pct=20.0,
        conversion_window_days=10,
        baseline_conversion_rate=0.140,
        treatment_effect_delta=0.045,
        baseline_mean_value=120.0,
        treatment_value_delta=5.0,
        refund_rate_control=0.010,
        refund_rate_treatment=0.009,
        payment_failure_control=0.007,
        payment_failure_treatment=0.007,
        complaint_rate_control=0.004,
        complaint_rate_treatment=0.004,
        scenario_tag="UNBALANCED_80_20_WIN",
    ),
    ExperimentBlueprint(
        index=5,
        name="Legacy Gateway Routing Experiment",
        description="Tests new payment gateway routing rule (hosts deliberate SRM and negative anomaly scenarios).",
        hypothesis="New payment routing increases completed checkout conversion by at least 2.0 percentage points.",
        primary_metric_suffix="CONV",
        primary_metric_name="Purchase Conversion Rate",
        primary_metric_type="Primary_Binary",
        calculation_method="ITT_Proportion",
        minimum_detectable_effect=0.02,
        control_allocation_pct=50.0,
        treatment_allocation_pct=50.0,
        conversion_window_days=7,
        baseline_conversion_rate=0.125,
        treatment_effect_delta=0.030,
        baseline_mean_value=64.0,
        treatment_value_delta=1.0,
        refund_rate_control=0.014,
        refund_rate_treatment=0.014,
        payment_failure_control=0.011,
        payment_failure_treatment=0.011,
        complaint_rate_control=0.005,
        complaint_rate_treatment=0.005,
        scenario_tag="ANOMALY_AND_SRM_HOST",
    ),
    ExperimentBlueprint(
        index=6,
        name="Minimalist Product Detail Header",
        description="Reduces visual clutter on product detail header to test impact on checkout conversion.",
        hypothesis="Minimalist header increases checkout conversion by at least 2.0 percentage points.",
        primary_metric_suffix="CONV",
        primary_metric_name="Purchase Conversion Rate",
        primary_metric_type="Primary_Binary",
        calculation_method="ITT_Proportion",
        minimum_detectable_effect=0.02,
        control_allocation_pct=50.0,
        treatment_allocation_pct=50.0,
        conversion_window_days=7,
        baseline_conversion_rate=0.130,
        treatment_effect_delta=0.002,  # Statistically insignificant noise
        baseline_mean_value=60.0,
        treatment_value_delta=0.0,
        refund_rate_control=0.013,
        refund_rate_treatment=0.013,
        payment_failure_control=0.009,
        payment_failure_treatment=0.009,
        complaint_rate_control=0.005,
        complaint_rate_treatment=0.005,
        scenario_tag="NO_SIGNIFICANT_LIFT",
    ),
    ExperimentBlueprint(
        index=7,
        name="Micro-Copy Button Color Adjustment",
        description="Tests high-contrast CTA button styling with a high predeclared MDE threshold (3.5 pp).",
        hypothesis="CTA styling increases conversion by at least 3.5 percentage points.",
        primary_metric_suffix="CONV",
        primary_metric_name="Purchase Conversion Rate",
        primary_metric_type="Primary_Binary",
        calculation_method="ITT_Proportion",
        minimum_detectable_effect=0.035,
        control_allocation_pct=50.0,
        treatment_allocation_pct=50.0,
        conversion_window_days=7,
        baseline_conversion_rate=0.100,
        treatment_effect_delta=0.022,  # Statistically significant (+2.2 pp) but below 3.5 pp MDE
        baseline_mean_value=55.0,
        treatment_value_delta=0.0,
        refund_rate_control=0.012,
        refund_rate_treatment=0.012,
        payment_failure_control=0.008,
        payment_failure_treatment=0.008,
        complaint_rate_control=0.004,
        complaint_rate_treatment=0.004,
        scenario_tag="SIGNIFICANT_BUT_BELOW_MDE",
    ),
    ExperimentBlueprint(
        index=8,
        name="Deferred BNPL Financing Prompt",
        description="Adds Buy-Now-Pay-Later financing option on checkout review step.",
        hypothesis="BNPL option increases checkout conversion by at least 2.0 percentage points.",
        primary_metric_suffix="CONV",
        primary_metric_name="Purchase Conversion Rate",
        primary_metric_type="Primary_Binary",
        calculation_method="ITT_Proportion",
        minimum_detectable_effect=0.02,
        control_allocation_pct=50.0,
        treatment_allocation_pct=50.0,
        conversion_window_days=14,
        baseline_conversion_rate=0.115,
        treatment_effect_delta=0.031,
        baseline_mean_value=85.0,
        treatment_value_delta=6.0,
        refund_rate_control=0.014,
        refund_rate_treatment=0.021,  # Triggers WARNING guardrail (+0.7 pp between +0.5 pp warning and +1.0 pp critical)
        payment_failure_control=0.010,
        payment_failure_treatment=0.010,
        complaint_rate_control=0.005,
        complaint_rate_treatment=0.005,
        scenario_tag="GUARDRAIL_WARNING_HOLD",
    ),
    ExperimentBlueprint(
        index=9,
        name="Localized Currency Auto-Detection",
        description="Automatically displays local currency symbols for international visitors (70:30 split).",
        hypothesis="Localized currency display improves conversion by at least 2.0 percentage points.",
        primary_metric_suffix="CONV",
        primary_metric_name="Purchase Conversion Rate",
        primary_metric_type="Primary_Binary",
        calculation_method="ITT_Proportion",
        minimum_detectable_effect=0.02,
        control_allocation_pct=70.0,
        treatment_allocation_pct=30.0,
        conversion_window_days=7,
        baseline_conversion_rate=0.105,
        treatment_effect_delta=0.034,
        baseline_mean_value=68.0,
        treatment_value_delta=3.0,
        refund_rate_control=0.013,
        refund_rate_treatment=0.012,
        payment_failure_control=0.009,
        payment_failure_treatment=0.008,
        complaint_rate_control=0.005,
        complaint_rate_treatment=0.004,
        scenario_tag="UNBALANCED_70_30_WIN",
    ),
    ExperimentBlueprint(
        index=10,
        name="Post-Purchase Instant Loyalty Enrollment",
        description="Tests instant loyalty points credit during checkout confirmation.",
        hypothesis="Instant loyalty credit increases conversion rate by at least 2.0 percentage points.",
        primary_metric_suffix="CONV",
        primary_metric_name="Purchase Conversion Rate",
        primary_metric_type="Primary_Binary",
        calculation_method="ITT_Proportion",
        minimum_detectable_effect=0.02,
        control_allocation_pct=50.0,
        treatment_allocation_pct=50.0,
        conversion_window_days=10,
        baseline_conversion_rate=0.122,
        treatment_effect_delta=0.029,
        baseline_mean_value=74.0,
        treatment_value_delta=2.5,
        refund_rate_control=0.014,
        refund_rate_treatment=0.013,
        payment_failure_control=0.009,
        payment_failure_treatment=0.009,
        complaint_rate_control=0.004,
        complaint_rate_treatment=0.004,
        scenario_tag="METRIC_VERSION_CHANGE_HOST",
    ),
)


def get_blueprints_for_config(
    config: DatasetScaleConfig,
) -> List[ExperimentBlueprint]:
    """Return the slice of experiment blueprints for the configured experiment_count."""
    count = config.experiment_count
    if count <= len(EXPERIMENT_BLUEPRINTS):
        return list(EXPERIMENT_BLUEPRINTS[:count])

    # If a custom configuration requests > 10 experiments, cycle blueprints deterministically
    result: List[ExperimentBlueprint] = []
    for idx in range(1, count + 1):
        template = EXPERIMENT_BLUEPRINTS[(idx - 1) % len(EXPERIMENT_BLUEPRINTS)]
        result.append(
            ExperimentBlueprint(
                index=idx,
                name=f"{template.name} (Wave {idx})",
                description=template.description,
                hypothesis=template.hypothesis,
                primary_metric_suffix=template.primary_metric_suffix,
                primary_metric_name=template.primary_metric_name,
                primary_metric_type=template.primary_metric_type,
                calculation_method=template.calculation_method,
                minimum_detectable_effect=template.minimum_detectable_effect,
                control_allocation_pct=template.control_allocation_pct,
                treatment_allocation_pct=template.treatment_allocation_pct,
                conversion_window_days=template.conversion_window_days,
                baseline_conversion_rate=template.baseline_conversion_rate,
                treatment_effect_delta=template.treatment_effect_delta,
                baseline_mean_value=template.baseline_mean_value,
                treatment_value_delta=template.treatment_value_delta,
                refund_rate_control=template.refund_rate_control,
                refund_rate_treatment=template.refund_rate_treatment,
                payment_failure_control=template.payment_failure_control,
                payment_failure_treatment=template.payment_failure_treatment,
                complaint_rate_control=template.complaint_rate_control,
                complaint_rate_treatment=template.complaint_rate_treatment,
                scenario_tag=template.scenario_tag,
            )
        )
    return result


def generate_master_data(
    session: Session,
    config: DatasetScaleConfig,
) -> Tuple[
    List[Experiment],
    List[Variant],
    List[MetricDefinition],
    List[GuardrailMetric],
]:
    """Execute Steps 1 & 2 (plus V1 metric and guardrail definitions) in strict dependency order."""
    blueprints = get_blueprints_for_config(config)
    experiments: List[Experiment] = []
    variants: List[Variant] = []
    metrics: List[MetricDefinition] = []
    guardrails: List[GuardrailMetric] = []
    events: List[ExperimentEvent] = []

    for bp in blueprints:
        exp_id = f"EXP-2026-{bp.index:06d}"
        primary_code = f"MET-{exp_id}-{bp.primary_metric_suffix}"
        ratio_str = f"{int(bp.control_allocation_pct)}:{int(bp.treatment_allocation_pct)}"

        # Step 1: Experiment Master Record (starts in Draft)
        exp = Experiment(
            experiment_id=exp_id,
            experiment_name=bp.name,
            description=bp.description,
            hypothesis=bp.hypothesis,
            primary_metric_code=primary_code,
            minimum_detectable_effect=bp.minimum_detectable_effect,
            significance_level=DEFAULT_SIGNIFICANCE_LEVEL,
            experiment_status="Draft",
            expected_allocation_ratio=ratio_str,
            start_date="2026-01-01T00:00:00Z",
            end_date="2026-01-31T23:59:59Z",
            conversion_window_days=bp.conversion_window_days,
            random_seed=config.random_seed,
            created_at=REFERENCE_EPOCH_ISO,
            updated_at=REFERENCE_EPOCH_ISO,
        )
        experiments.append(exp)

        events.append(
            ExperimentEvent(
                event_id=f"EVT-{exp_id}-001",
                experiment_id=exp_id,
                event_type="Experiment_Created",
                from_status=None,
                to_status="Draft",
                actor="Data_Analyst",
                notes=f"Created experiment {exp_id} in Draft state",
                event_timestamp=REFERENCE_EPOCH_ISO,
            )
        )

        # Step 2: Variant Records (Control A and Treatment B)
        var_a = Variant(
            variant_id=f"VAR-{exp_id}-A",
            experiment_id=exp_id,
            variant_name="A",
            variant_type="Control",
            allocation_percentage=bp.control_allocation_pct,
            description=f"Control baseline experience for {bp.name}",
            created_at=REFERENCE_EPOCH_ISO,
        )
        var_b = Variant(
            variant_id=f"VAR-{exp_id}-B",
            experiment_id=exp_id,
            variant_name="B",
            variant_type="Treatment",
            allocation_percentage=bp.treatment_allocation_pct,
            description=f"Treatment candidate experience for {bp.name}",
            created_at=REFERENCE_EPOCH_ISO,
        )
        variants.extend([var_a, var_b])

        # Primary Metric Definition (Version 1)
        primary_metric_id = f"{primary_code}-V1"
        metrics.append(
            MetricDefinition(
                metric_id=primary_metric_id,
                experiment_id=exp_id,
                metric_code=primary_code,
                metric_name=bp.primary_metric_name,
                metric_type=bp.primary_metric_type,
                metric_description=f"Primary evaluation metric ({bp.primary_metric_name}) for {exp_id}",
                numerator_definition=(
                    "Distinct assigned users with valid Purchase conversion within conversion_window_days"
                    if bp.primary_metric_type == "Primary_Binary"
                    else "Sum of valid Purchase conversion_value within conversion_window_days"
                ),
                denominator_definition="Total eligible assigned users (ITT population)",
                calculation_method=bp.calculation_method,
                metric_version=1,
                effective_from=REFERENCE_EPOCH_ISO,
                created_at=REFERENCE_EPOCH_ISO,
            )
        )

        # Guardrail Metric Definitions (Refund Rate, Payment Failure Rate, Complaint Rate)
        refund_code = f"MET-{exp_id}-REFUND"
        refund_met_id = f"{refund_code}-V1"
        metrics.append(
            MetricDefinition(
                metric_id=refund_met_id,
                experiment_id=exp_id,
                metric_code=refund_code,
                metric_name="Refund Rate",
                metric_type="Guardrail_Rate",
                metric_description="Proportion of assigned users experiencing a Refund event",
                numerator_definition="Distinct assigned users with valid Refund event",
                denominator_definition="Total eligible assigned users (ITT population)",
                calculation_method="ITT_Proportion",
                metric_version=1,
                effective_from=REFERENCE_EPOCH_ISO,
                created_at=REFERENCE_EPOCH_ISO,
            )
        )

        payfail_code = f"MET-{exp_id}-PAYFAIL"
        payfail_met_id = f"{payfail_code}-V1"
        metrics.append(
            MetricDefinition(
                metric_id=payfail_met_id,
                experiment_id=exp_id,
                metric_code=payfail_code,
                metric_name="Payment Failure Rate",
                metric_type="Guardrail_Rate",
                metric_description="Proportion of assigned users experiencing a Payment_Failure event",
                numerator_definition="Distinct assigned users with valid Payment_Failure event",
                denominator_definition="Total eligible assigned users (ITT population)",
                calculation_method="ITT_Proportion",
                metric_version=1,
                effective_from=REFERENCE_EPOCH_ISO,
                created_at=REFERENCE_EPOCH_ISO,
            )
        )

        complaint_code = f"MET-{exp_id}-COMPLAINT"
        complaint_met_id = f"{complaint_code}-V1"
        metrics.append(
            MetricDefinition(
                metric_id=complaint_met_id,
                experiment_id=exp_id,
                metric_code=complaint_code,
                metric_name="Customer Complaint Rate",
                metric_type="Guardrail_Rate",
                metric_description="Proportion of assigned users filing a Complaint event",
                numerator_definition="Distinct assigned users with valid Complaint event",
                denominator_definition="Total eligible assigned users (ITT population)",
                calculation_method="ITT_Proportion",
                metric_version=1,
                effective_from=REFERENCE_EPOCH_ISO,
                created_at=REFERENCE_EPOCH_ISO,
            )
        )

        # Guardrail Threshold Configurations (Warning + Critical for Refund, Critical for Payment Failure & Complaint)
        guardrails.extend(
            [
                GuardrailMetric(
                    guardrail_id=f"GRD-{exp_id}-01",
                    experiment_id=exp_id,
                    metric_id=refund_met_id,
                    metric_version=1,
                    guardrail_name="Refund Rate Warning (+0.5 pp)",
                    threshold_type="Absolute_Diff",
                    threshold_value=0.005,
                    comparison_direction="MAX_INCREASE",
                    severity="WARNING",
                    created_at=REFERENCE_EPOCH_ISO,
                ),
                GuardrailMetric(
                    guardrail_id=f"GRD-{exp_id}-02",
                    experiment_id=exp_id,
                    metric_id=refund_met_id,
                    metric_version=1,
                    guardrail_name="Refund Rate Critical (+1.0 pp)",
                    threshold_type="Absolute_Diff",
                    threshold_value=0.010,
                    comparison_direction="MAX_INCREASE",
                    severity="CRITICAL",
                    created_at=REFERENCE_EPOCH_ISO,
                ),
                GuardrailMetric(
                    guardrail_id=f"GRD-{exp_id}-03",
                    experiment_id=exp_id,
                    metric_id=payfail_met_id,
                    metric_version=1,
                    guardrail_name="Payment Failure Critical (+0.8 pp)",
                    threshold_type="Absolute_Diff",
                    threshold_value=0.008,
                    comparison_direction="MAX_INCREASE",
                    severity="CRITICAL",
                    created_at=REFERENCE_EPOCH_ISO,
                ),
                GuardrailMetric(
                    guardrail_id=f"GRD-{exp_id}-04",
                    experiment_id=exp_id,
                    metric_id=complaint_met_id,
                    metric_version=1,
                    guardrail_name="Customer Complaint Critical (+0.8 pp)",
                    threshold_type="Absolute_Diff",
                    threshold_value=0.008,
                    comparison_direction="MAX_INCREASE",
                    severity="CRITICAL",
                    created_at=REFERENCE_EPOCH_ISO,
                ),
            ]
        )

    session.add_all(experiments)
    session.flush()
    session.add_all(variants)
    session.add_all(metrics)
    session.flush()
    session.add_all(guardrails)
    session.add_all(events)
    session.flush()

    return experiments, variants, metrics, guardrails