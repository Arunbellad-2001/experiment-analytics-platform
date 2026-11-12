"""Experiment lifecycle governance, parameter validation, and audit logging service."""

from __future__ import annotations

from typing import List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from config.settings import (
    ALLOWED_EXPERIMENT_STATUSES,
    ALLOWED_LIFECYCLE_TRANSITIONS,
    ALLOWED_METRIC_TYPES,
    ALLOWED_VARIANT_TYPES,
    REFERENCE_EPOCH_ISO,
)
from database.models import (
    Experiment,
    ExperimentEvent,
    ExperimentResult,
    MetricDefinition,
    Variant,
)


def validate_mde_for_metric_type(mde: float, metric_type: str) -> None:
    """Validate predeclared MDE scale according to the primary metric type."""
    if metric_type not in ALLOWED_METRIC_TYPES:
        raise ValueError(f"Unsupported metric_type: {metric_type}")
    if metric_type == "Guardrail_Rate":
        raise ValueError(
            "Guardrail_Rate metric cannot be used as an experiment primary metric."
        )
    if mde < 0.0:
        raise ValueError(
            f"minimum_detectable_effect must be non-negative (got {mde})."
        )
    if metric_type == "Primary_Binary" and mde > 1.0:
        raise ValueError(
            f"Primary_Binary metrics require 0.0 <= minimum_detectable_effect <= 1.0 (got {mde})."
        )


def validate_experiment_variants(
    variants: Sequence[Variant], tol: float = 1e-5
) -> Variant:
    """Verify an experiment has at least 2 variants, exactly 1 Control, and 100% total allocation."""
    if len(variants) < 2:
        raise ValueError("An experiment must have at least 2 variants (Control and Treatment).")

    control_variants = [v for v in variants if v.variant_type == "Control"]
    if len(control_variants) != 1:
        raise ValueError(
            f"An experiment must have exactly one Control variant (found {len(control_variants)})."
        )

    for v in variants:
        if v.variant_type not in ALLOWED_VARIANT_TYPES:
            raise ValueError(f"Invalid variant_type: {v.variant_type}")
        if v.allocation_percentage <= 0.0 or v.allocation_percentage > 100.0:
            raise ValueError(
                f"Variant {v.variant_id} allocation_percentage out of range: {v.allocation_percentage}"
            )

    total_alloc = sum(v.allocation_percentage for v in variants)
    if abs(total_alloc - 100.0) > tol:
        raise ValueError(
            f"Variant allocation percentages must sum to 100.0 (got {total_alloc:.4f})."
        )

    return control_variants[0]


def validate_primary_metric_exists(
    session: Session, experiment: Experiment
) -> MetricDefinition:
    """Verify the experiment's primary_metric_code resolves to a valid primary MetricDefinition."""
    stmt = (
        select(MetricDefinition)
        .where(
            MetricDefinition.experiment_id == experiment.experiment_id,
            MetricDefinition.metric_code == experiment.primary_metric_code,
        )
        .order_by(MetricDefinition.metric_version.asc())
    )
    definitions = list(session.scalars(stmt).all())
    if not definitions:
        raise ValueError(
            f"Experiment {experiment.experiment_id} primary_metric_code "
            f"'{experiment.primary_metric_code}' does not exist in metric_definitions."
        )

    latest_def = definitions[-1]
    validate_mde_for_metric_type(
        experiment.minimum_detectable_effect, latest_def.metric_type
    )
    return latest_def


def update_predeclared_parameters(
    session: Session,
    experiment_id: str,
    minimum_detectable_effect: Optional[float] = None,
    significance_level: Optional[float] = None,
    primary_metric_code: Optional[str] = None,
    updated_at: str = REFERENCE_EPOCH_ISO,
) -> Experiment:
    """Update predeclared parameters only while experiment is in Draft and no results exist."""
    experiment = session.get(Experiment, experiment_id)
    if experiment is None:
        raise ValueError(f"Experiment not found: {experiment_id}")

    if experiment.experiment_status != "Draft":
        raise ValueError(
            f"Cannot modify predeclared parameters when experiment_status is '{experiment.experiment_status}'. "
            "Parameters are locked outside Draft."
        )

    has_results = session.scalar(
        select(ExperimentResult.result_id)
        .where(ExperimentResult.experiment_id == experiment_id)
        .limit(1)
    )
    if has_results is not None:
        raise ValueError(
            "Cannot modify predeclared parameters after analysis results have been recorded."
        )

    target_code = (
        primary_metric_code
        if primary_metric_code is not None
        else experiment.primary_metric_code
    )
    target_mde = (
        minimum_detectable_effect
        if minimum_detectable_effect is not None
        else experiment.minimum_detectable_effect
    )

    if significance_level is not None:
        if not (0.0 < significance_level < 1.0):
            raise ValueError("significance_level must be strictly between 0.0 and 1.0.")
        experiment.significance_level = significance_level

    # Check if metric definition already exists to validate MDE scale
    existing_metric = session.scalar(
        select(MetricDefinition)
        .where(
            MetricDefinition.experiment_id == experiment_id,
            MetricDefinition.metric_code == target_code,
        )
        .order_by(MetricDefinition.metric_version.desc())
        .limit(1)
    )
    if existing_metric is not None:
        validate_mde_for_metric_type(target_mde, existing_metric.metric_type)
    elif target_mde < 0.0:
        raise ValueError("minimum_detectable_effect must be non-negative.")

    experiment.primary_metric_code = target_code
    experiment.minimum_detectable_effect = target_mde
    experiment.updated_at = updated_at
    session.flush()
    return experiment


def transition_experiment_status(
    session: Session,
    experiment_id: str,
    target_status: str,
    actor: str = "System_Admin",
    event_timestamp: str = REFERENCE_EPOCH_ISO,
    notes: str = "",
) -> Experiment:
    """Transition an experiment along the strict lifecycle state machine and record an ExperimentEvent."""
    if target_status not in ALLOWED_EXPERIMENT_STATUSES:
        raise ValueError(f"Unsupported experiment_status: {target_status}")

    experiment = session.get(Experiment, experiment_id)
    if experiment is None:
        raise ValueError(f"Experiment not found: {experiment_id}")

    current_status = experiment.experiment_status
    if current_status != "Draft" and target_status == "Draft":
        raise ValueError(
            "Invalid lifecycle transition: an experiment cannot return to Draft after leaving Draft status."
        )

    allowed_targets = ALLOWED_LIFECYCLE_TRANSITIONS.get(current_status, frozenset())
    if target_status not in allowed_targets:
        raise ValueError(
            f"Invalid experiment_status lifecycle transition: '{current_status}' -> '{target_status}'."
        )

    # Before leaving Draft -> Ready, validate variants (exactly 1 Control) and primary metric
    if current_status == "Draft" and target_status == "Ready":
        variants = list(
            session.scalars(
                select(Variant).where(Variant.experiment_id == experiment_id)
            ).all()
        )
        validate_experiment_variants(variants)
        validate_primary_metric_exists(session, experiment)

    experiment.experiment_status = target_status
    experiment.updated_at = event_timestamp

    existing_events_count = len(
        list(
            session.scalars(
                select(ExperimentEvent.event_id).where(
                    ExperimentEvent.experiment_id == experiment_id
                )
            ).all()
        )
    )
    event_id = f"EVT-{experiment_id}-{existing_events_count + 1:03d}"
    audit_event = ExperimentEvent(
        event_id=event_id,
        experiment_id=experiment_id,
        event_type="State_Transition",
        from_status=current_status,
        to_status=target_status,
        actor=actor,
        notes=notes or f"Transitioned from {current_status} to {target_status}",
        event_timestamp=event_timestamp,
    )
    session.add(audit_event)
    session.flush()
    return experiment


def get_control_variant(session: Session, experiment_id: str) -> Variant:
    """Return the unique Control variant for the given experiment."""
    variants = list(
        session.scalars(
            select(Variant).where(Variant.experiment_id == experiment_id)
        ).all()
    )
    return validate_experiment_variants(variants)