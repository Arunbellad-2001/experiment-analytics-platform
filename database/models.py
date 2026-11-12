"""SQLAlchemy 2.0 ORM models mirroring the authoritative database/schema.sql definition."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base class for all operational ORM entities."""


class Experiment(Base):
    """Entity 1: Experiment master record and lifecycle state container."""

    __tablename__ = "experiments"
    __table_args__ = (
        CheckConstraint("minimum_detectable_effect >= 0.0", name="ck_exp_mde_non_neg"),
        CheckConstraint(
            "significance_level > 0.0 AND significance_level < 1.0",
            name="ck_exp_alpha_bounds",
        ),
        CheckConstraint(
            "experiment_status IN ('Draft', 'Ready', 'Running', 'Paused', 'Completed', 'Archived')",
            name="ck_exp_status_enum",
        ),
        CheckConstraint("conversion_window_days > 0", name="ck_exp_conv_window_pos"),
        CheckConstraint("start_date <= end_date", name="ck_exp_date_order"),
        Index("idx_experiments_status", "experiment_status"),
    )

    experiment_id: Mapped[str] = mapped_column(String, primary_key=True)
    experiment_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    hypothesis: Mapped[str] = mapped_column(String, nullable=False)
    primary_metric_code: Mapped[str] = mapped_column(String, nullable=False)
    minimum_detectable_effect: Mapped[float] = mapped_column(Float, nullable=False)
    significance_level: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.05
    )
    experiment_status: Mapped[str] = mapped_column(String, nullable=False)
    expected_allocation_ratio: Mapped[str] = mapped_column(String, nullable=False)
    start_date: Mapped[str] = mapped_column(String, nullable=False)
    end_date: Mapped[str] = mapped_column(String, nullable=False)
    conversion_window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)

    variants: Mapped[List["Variant"]] = relationship(
        "Variant", back_populates="experiment", cascade="all, delete-orphan"
    )
    assignments: Mapped[List["Assignment"]] = relationship(
        "Assignment", back_populates="experiment"
    )
    exposure_events: Mapped[List["ExposureEvent"]] = relationship(
        "ExposureEvent", back_populates="experiment"
    )
    conversion_events: Mapped[List["ConversionEvent"]] = relationship(
        "ConversionEvent", back_populates="experiment"
    )
    metric_definitions: Mapped[List["MetricDefinition"]] = relationship(
        "MetricDefinition", back_populates="experiment"
    )
    guardrail_metrics: Mapped[List["GuardrailMetric"]] = relationship(
        "GuardrailMetric", back_populates="experiment"
    )
    experiment_results: Mapped[List["ExperimentResult"]] = relationship(
        "ExperimentResult", back_populates="experiment"
    )
    experiment_events: Mapped[List["ExperimentEvent"]] = relationship(
        "ExperimentEvent", back_populates="experiment"
    )
    experiment_issues: Mapped[List["ExperimentIssue"]] = relationship(
        "ExperimentIssue", back_populates="experiment"
    )


class Variant(Base):
    """Entity 2: Experiment treatment or control variant configuration."""

    __tablename__ = "variants"
    __table_args__ = (
        CheckConstraint(
            "variant_type IN ('Control', 'Treatment')", name="ck_variant_type_enum"
        ),
        CheckConstraint(
            "allocation_percentage > 0.0 AND allocation_percentage <= 100.0",
            name="ck_variant_alloc_bounds",
        ),
        UniqueConstraint("experiment_id", "variant_name", name="uq_variant_exp_name"),
        UniqueConstraint("experiment_id", "variant_id", name="uq_variant_exp_id"),
        UniqueConstraint(
            "experiment_id", "variant_id", "variant_type", name="uq_variant_exp_id_type"
        ),
        Index(
            "idx_variants_single_control",
            "experiment_id",
            unique=True,
            sqlite_where=text("variant_type = 'Control'"),
        ),
        Index("idx_variants_experiment", "experiment_id"),
    )

    variant_id: Mapped[str] = mapped_column(String, primary_key=True)
    experiment_id: Mapped[str] = mapped_column(
        String, ForeignKey("experiments.experiment_id"), nullable=False
    )
    variant_name: Mapped[str] = mapped_column(String, nullable=False)
    variant_type: Mapped[str] = mapped_column(String, nullable=False)
    allocation_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    experiment: Mapped["Experiment"] = relationship(
        "Experiment", back_populates="variants"
    )


class AudienceMember(Base):
    """Entity 3: Synthetic user profile and eligibility record."""

    __tablename__ = "audience_members"
    __table_args__ = (
        CheckConstraint(
            "eligibility_status IN ('Eligible', 'Ineligible')",
            name="ck_audience_eligibility_enum",
        ),
        Index("idx_audience_eligibility", "eligibility_status"),
        Index("idx_audience_segment", "user_segment"),
    )

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_segment: Mapped[str] = mapped_column(String, nullable=False)
    eligibility_status: Mapped[str] = mapped_column(String, nullable=False)
    registration_date: Mapped[str] = mapped_column(String, nullable=False)
    country_region: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class Assignment(Base):
    """Entity 4: Randomized assignment of an audience member to an experiment variant."""

    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint(
            "assignment_status IN ('Assigned', 'Duplicate_Anomaly')",
            name="ck_assignment_status_enum",
        ),
        ForeignKeyConstraint(
            ["experiment_id", "variant_id"],
            ["variants.experiment_id", "variants.variant_id"],
            name="fk_assignment_exp_variant",
        ),
        UniqueConstraint(
            "assignment_id",
            "experiment_id",
            "user_id",
            "variant_id",
            name="uq_assignment_full_composite",
        ),
        UniqueConstraint(
            "assignment_id",
            "experiment_id",
            "user_id",
            name="uq_assignment_exp_user_composite",
        ),
        Index("idx_assignments_exp_user", "experiment_id", "user_id"),
        Index("idx_assignments_exp_variant", "experiment_id", "variant_id"),
    )

    assignment_id: Mapped[str] = mapped_column(String, primary_key=True)
    experiment_id: Mapped[str] = mapped_column(
        String, ForeignKey("experiments.experiment_id"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("audience_members.user_id"), nullable=False
    )
    variant_id: Mapped[str] = mapped_column(String, nullable=False)
    assigned_at: Mapped[str] = mapped_column(String, nullable=False)
    assignment_status: Mapped[str] = mapped_column(String, nullable=False)
    randomization_seed: Mapped[int] = mapped_column(Integer, nullable=False)

    experiment: Mapped["Experiment"] = relationship(
        "Experiment", back_populates="assignments"
    )


class ExposureEvent(Base):
    """Entity 5: Telemetry record of a user encountering an experiment variant."""

    __tablename__ = "exposure_events"
    __table_args__ = (
        CheckConstraint(
            "exposure_status IN ('Exposed', 'Failed', 'Noncompliant', 'Invalid_Order')",
            name="ck_exposure_status_enum",
        ),
        CheckConstraint(
            "telemetry_status IN ('Complete', 'Missing', 'Delayed')",
            name="ck_exposure_telemetry_enum",
        ),
        ForeignKeyConstraint(
            ["experiment_id", "variant_id"],
            ["variants.experiment_id", "variants.variant_id"],
            name="fk_exposure_exp_variant",
        ),
        ForeignKeyConstraint(
            ["assignment_id", "experiment_id", "user_id", "variant_id"],
            [
                "assignments.assignment_id",
                "assignments.experiment_id",
                "assignments.user_id",
                "assignments.variant_id",
            ],
            name="fk_exposure_assignment_composite",
        ),
        Index("idx_exposures_exp_variant", "experiment_id", "variant_id"),
        Index("idx_exposures_assignment", "assignment_id"),
    )

    exposure_id: Mapped[str] = mapped_column(String, primary_key=True)
    experiment_id: Mapped[str] = mapped_column(
        String, ForeignKey("experiments.experiment_id"), nullable=False
    )
    assignment_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("audience_members.user_id"), nullable=False
    )
    variant_id: Mapped[str] = mapped_column(String, nullable=False)
    exposure_timestamp: Mapped[str] = mapped_column(String, nullable=False)
    exposure_status: Mapped[str] = mapped_column(String, nullable=False)
    telemetry_status: Mapped[str] = mapped_column(String, nullable=False)

    experiment: Mapped["Experiment"] = relationship(
        "Experiment", back_populates="exposure_events"
    )


class ConversionEvent(Base):
    """Entity 6: Primary outcome or negative guardrail event recorded for a user."""

    __tablename__ = "conversion_events"
    __table_args__ = (
        CheckConstraint(
            "conversion_type IN ('Purchase', 'Refund', 'Payment_Failure', 'Complaint')",
            name="ck_conversion_type_enum",
        ),
        CheckConstraint(
            "conversion_status IN ('Valid', 'Delayed_In_Window', 'Outside_Window', 'Incomplete_Telemetry')",
            name="ck_conversion_status_enum",
        ),
        ForeignKeyConstraint(
            ["assignment_id", "experiment_id", "user_id"],
            [
                "assignments.assignment_id",
                "assignments.experiment_id",
                "assignments.user_id",
            ],
            name="fk_conversion_assignment_composite",
        ),
        Index("idx_conversions_exp_user", "experiment_id", "user_id"),
        Index("idx_conversions_exp_type", "experiment_id", "conversion_type"),
    )

    conversion_id: Mapped[str] = mapped_column(String, primary_key=True)
    experiment_id: Mapped[str] = mapped_column(
        String, ForeignKey("experiments.experiment_id"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("audience_members.user_id"), nullable=False
    )
    assignment_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    conversion_type: Mapped[str] = mapped_column(String, nullable=False)
    conversion_timestamp: Mapped[str] = mapped_column(String, nullable=False)
    conversion_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    conversion_status: Mapped[str] = mapped_column(String, nullable=False)

    experiment: Mapped["Experiment"] = relationship(
        "Experiment", back_populates="conversion_events"
    )


class MetricDefinition(Base):
    """Entity 7: Strictly append-only versioned metric formula definition."""

    __tablename__ = "metric_definitions"
    __table_args__ = (
        CheckConstraint(
            "metric_type IN ('Primary_Binary', 'Primary_Continuous', 'Guardrail_Rate')",
            name="ck_metric_type_enum",
        ),
        CheckConstraint(
            "calculation_method IN ('ITT_Proportion', 'Exposed_Proportion', 'ITT_Mean_Value')",
            name="ck_metric_calc_method_enum",
        ),
        CheckConstraint("metric_version >= 1", name="ck_metric_version_pos"),
        UniqueConstraint(
            "experiment_id",
            "metric_code",
            "metric_version",
            name="uq_metric_exp_code_ver",
        ),
        UniqueConstraint(
            "metric_id",
            "experiment_id",
            "metric_version",
            name="uq_metric_id_exp_ver",
        ),
        Index(
            "idx_metrics_exp_code_ver",
            "experiment_id",
            "metric_code",
            "metric_version",
        ),
    )

    metric_id: Mapped[str] = mapped_column(String, primary_key=True)
    experiment_id: Mapped[str] = mapped_column(
        String, ForeignKey("experiments.experiment_id"), nullable=False
    )
    metric_code: Mapped[str] = mapped_column(String, nullable=False)
    metric_name: Mapped[str] = mapped_column(String, nullable=False)
    metric_type: Mapped[str] = mapped_column(String, nullable=False)
    metric_description: Mapped[str] = mapped_column(String, nullable=False)
    numerator_definition: Mapped[str] = mapped_column(String, nullable=False)
    denominator_definition: Mapped[str] = mapped_column(String, nullable=False)
    calculation_method: Mapped[str] = mapped_column(String, nullable=False)
    metric_version: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    experiment: Mapped["Experiment"] = relationship(
        "Experiment", back_populates="metric_definitions"
    )


class GuardrailMetric(Base):
    """Entity 8: Configurable safety threshold protecting business outcomes."""

    __tablename__ = "guardrail_metrics"
    __table_args__ = (
        CheckConstraint(
            "threshold_type IN ('Absolute_Diff', 'Relative_Lift', 'Max_Rate')",
            name="ck_guardrail_threshold_type_enum",
        ),
        CheckConstraint(
            "comparison_direction IN ('MAX_INCREASE', 'MIN_DECREASE', 'ABSOLUTE_CAP')",
            name="ck_guardrail_direction_enum",
        ),
        CheckConstraint(
            "severity IN ('WARNING', 'CRITICAL')", name="ck_guardrail_severity_enum"
        ),
        ForeignKeyConstraint(
            ["metric_id", "experiment_id", "metric_version"],
            [
                "metric_definitions.metric_id",
                "metric_definitions.experiment_id",
                "metric_definitions.metric_version",
            ],
            name="fk_guardrail_metric_composite",
        ),
        Index("idx_guardrails_experiment", "experiment_id"),
    )

    guardrail_id: Mapped[str] = mapped_column(String, primary_key=True)
    experiment_id: Mapped[str] = mapped_column(
        String, ForeignKey("experiments.experiment_id"), nullable=False
    )
    metric_id: Mapped[str] = mapped_column(String, nullable=False)
    metric_version: Mapped[int] = mapped_column(Integer, nullable=False)
    guardrail_name: Mapped[str] = mapped_column(String, nullable=False)
    threshold_type: Mapped[str] = mapped_column(String, nullable=False)
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    comparison_direction: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    experiment: Mapped["Experiment"] = relationship(
        "Experiment", back_populates="guardrail_metrics"
    )


class ExperimentResult(Base):
    """Entity 9: Strictly append-only snapshot of variant metrics and statistical comparisons."""

    __tablename__ = "experiment_results"
    __table_args__ = (
        CheckConstraint("control_variant_type = 'Control'", name="ck_res_ctrl_type"),
        CheckConstraint(
            "analysis_method IN ('ITT', 'EXPOSED_SECONDARY')",
            name="ck_res_analysis_method_enum",
        ),
        CheckConstraint("sample_size >= 0", name="ck_res_sample_size_non_neg"),
        CheckConstraint("denominator >= 0.0", name="ck_res_denominator_non_neg"),
        CheckConstraint(
            "standard_error IS NULL OR standard_error >= 0.0",
            name="ck_res_se_non_neg",
        ),
        CheckConstraint(
            "p_value IS NULL OR (p_value >= 0.0 AND p_value <= 1.0)",
            name="ck_res_pvalue_bounds",
        ),
        CheckConstraint(
            "statistical_significance IS NULL OR statistical_significance IN (0, 1)",
            name="ck_res_stat_sig_bool",
        ),
        CheckConstraint(
            "guardrail_status IN ('PASSED', 'WARNING', 'FAILED', 'INSUFFICIENT_DATA', 'NOT_APPLICABLE')",
            name="ck_res_guardrail_status_enum",
        ),
        CheckConstraint(
            "decision_status IN ("
            "'CONTROL_BASELINE', "
            "'LAUNCH_TREATMENT', "
            "'HOLD_FOR_GUARDRAIL_REVIEW', "
            "'INSUFFICIENT_GUARDRAIL_DATA', "
            "'DO_NOT_LAUNCH_NO_SIGNIFICANT_LIFT', "
            "'DO_NOT_LAUNCH_BELOW_MDE', "
            "'DO_NOT_LAUNCH_GUARDRAIL_BREACH', "
            "'INVALID_DATA_HOLD', "
            "'RECALCULATION_REQUIRED'"
            ")",
            name="ck_res_decision_status_enum",
        ),
        CheckConstraint(
            "("
            "variant_id = control_variant_id "
            "AND treatment_effect IS NULL "
            "AND relative_lift IS NULL "
            "AND standard_error IS NULL "
            "AND confidence_interval_lower IS NULL "
            "AND confidence_interval_upper IS NULL "
            "AND p_value IS NULL "
            "AND statistical_significance IS NULL "
            "AND decision_status = 'CONTROL_BASELINE'"
            ") OR ("
            "variant_id <> control_variant_id "
            "AND treatment_effect IS NOT NULL "
            "AND (denominator = 0.0 OR relative_lift IS NOT NULL) "
            "AND standard_error IS NOT NULL "
            "AND standard_error >= 0.0 "
            "AND confidence_interval_lower IS NOT NULL "
            "AND confidence_interval_upper IS NOT NULL "
            "AND confidence_interval_lower <= treatment_effect "
            "AND treatment_effect <= confidence_interval_upper "
            "AND p_value IS NOT NULL "
            "AND p_value >= 0.0 "
            "AND p_value <= 1.0 "
            "AND statistical_significance IS NOT NULL "
            "AND decision_status <> 'CONTROL_BASELINE'"
            ")",
            name="ck_res_control_vs_treatment_grain",
        ),
        ForeignKeyConstraint(
            ["experiment_id", "variant_id"],
            ["variants.experiment_id", "variants.variant_id"],
            name="fk_result_exp_variant",
        ),
        ForeignKeyConstraint(
            ["experiment_id", "control_variant_id", "control_variant_type"],
            [
                "variants.experiment_id",
                "variants.variant_id",
                "variants.variant_type",
            ],
            name="fk_result_exp_control_variant",
        ),
        ForeignKeyConstraint(
            ["metric_id", "experiment_id", "metric_version"],
            [
                "metric_definitions.metric_id",
                "metric_definitions.experiment_id",
                "metric_definitions.metric_version",
            ],
            name="fk_result_metric_composite",
        ),
        UniqueConstraint(
            "analysis_run_id",
            "experiment_id",
            "variant_id",
            "metric_id",
            "metric_version",
            "analysis_method",
            name="uq_result_run_grain",
        ),
        Index("idx_results_exp_run", "experiment_id", "analysis_run_id"),
    )

    result_id: Mapped[str] = mapped_column(String, primary_key=True)
    analysis_run_id: Mapped[str] = mapped_column(String, nullable=False)
    experiment_id: Mapped[str] = mapped_column(
        String, ForeignKey("experiments.experiment_id"), nullable=False
    )
    variant_id: Mapped[str] = mapped_column(String, nullable=False)
    control_variant_id: Mapped[str] = mapped_column(String, nullable=False)
    control_variant_type: Mapped[str] = mapped_column(
        String, nullable=False, default="Control"
    )
    metric_id: Mapped[str] = mapped_column(String, nullable=False)
    metric_version: Mapped[int] = mapped_column(Integer, nullable=False)
    analysis_method: Mapped[str] = mapped_column(String, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    numerator: Mapped[float] = mapped_column(Float, nullable=False)
    denominator: Mapped[float] = mapped_column(Float, nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    treatment_effect: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    relative_lift: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    standard_error: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_interval_lower: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    confidence_interval_upper: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    p_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    statistical_significance: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    guardrail_status: Mapped[str] = mapped_column(String, nullable=False)
    decision_status: Mapped[str] = mapped_column(String, nullable=False)
    analysis_timestamp: Mapped[str] = mapped_column(String, nullable=False)

    experiment: Mapped["Experiment"] = relationship(
        "Experiment", back_populates="experiment_results"
    )


class ExperimentEvent(Base):
    """Supporting Entity 10: Lifecycle state-change and operational audit history."""

    __tablename__ = "experiment_events"
    __table_args__ = (Index("idx_events_experiment", "experiment_id"),)

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    experiment_id: Mapped[str] = mapped_column(
        String, ForeignKey("experiments.experiment_id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    to_status: Mapped[str] = mapped_column(String, nullable=False)
    actor: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str] = mapped_column(String, nullable=False)
    event_timestamp: Mapped[str] = mapped_column(String, nullable=False)

    experiment: Mapped["Experiment"] = relationship(
        "Experiment", back_populates="experiment_events"
    )


class ExperimentIssue(Base):
    """Supporting Entity 11: Operational anomaly and validation issue log (zero ground-truth columns)."""

    __tablename__ = "experiment_issues"
    __table_args__ = (
        CheckConstraint(
            "issue_type IN ("
            "'DUPLICATE_ASSIGNMENT', "
            "'EXPOSURE_BEFORE_ASSIGNMENT', "
            "'OUTCOME_WINDOW_VIOLATION', "
            "'SRM_DETECTED', "
            "'METRIC_VERSION_MISMATCH'"
            ")",
            name="ck_issue_type_enum",
        ),
        CheckConstraint(
            "severity IN ('WARNING', 'CRITICAL')", name="ck_issue_severity_enum"
        ),
        CheckConstraint(
            "resolution_status IN ('Open', 'Acknowledged', 'Resolved')",
            name="ck_issue_resolution_enum",
        ),
        Index("idx_issues_exp_type", "experiment_id", "issue_type"),
    )

    issue_id: Mapped[str] = mapped_column(String, primary_key=True)
    experiment_id: Mapped[str] = mapped_column(
        String, ForeignKey("experiments.experiment_id"), nullable=False
    )
    affected_entity: Mapped[str] = mapped_column(String, nullable=False)
    affected_record_id: Mapped[str] = mapped_column(String, nullable=False)
    issue_type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    detected_at: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    expected_behavior: Mapped[str] = mapped_column(String, nullable=False)
    actual_behavior: Mapped[str] = mapped_column(String, nullable=False)
    resolution_status: Mapped[str] = mapped_column(String, nullable=False)

    experiment: Mapped["Experiment"] = relationship(
        "Experiment", back_populates="experiment_issues"
    )