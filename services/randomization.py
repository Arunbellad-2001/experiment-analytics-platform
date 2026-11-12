"""Reproducible user-to-variant randomization engine and Chi-square SRM validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence

import numpy as np
from scipy.stats import chisquare
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config.settings import DEFAULT_RANDOM_SEED, DEFAULT_SRM_ALPHA, REFERENCE_EPOCH_ISO
from database.models import (
    Assignment,
    AudienceMember,
    Experiment,
    ExperimentIssue,
    Variant,
)
from services.experiment_service import validate_experiment_variants


@dataclass(frozen=True)
class VariantAllocationSummary:
    """Per-variant sample ratio summary."""

    variant_id: str
    variant_name: str
    variant_type: str
    expected_percentage: float
    actual_percentage: float
    expected_count: float
    actual_count: int
    absolute_percentage_diff: float


@dataclass(frozen=True)
class RandomizationValidationResult:
    """Complete randomization & Sample Ratio Mismatch (SRM) validation output."""

    experiment_id: str
    total_assigned: int
    chi2_statistic: float
    srm_p_value: float
    srm_alpha: float
    srm_detected: bool
    validation_status: str
    variant_summaries: List[VariantAllocationSummary]


def assign_eligible_users(
    session: Session,
    experiment_id: str,
    candidate_users: Sequence[AudienceMember],
    seed: int = DEFAULT_RANDOM_SEED,
    override_probabilities: Optional[Sequence[float]] = None,
    persist: bool = True,
) -> List[Assignment]:
    """Deterministically assign only Eligible users to experiment variants without baseline duplicates."""
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
    validate_experiment_variants(variants)

    # Filter strictly to Eligible users and sort deterministically by user_id
    eligible_users = sorted(
        [u for u in candidate_users if u.eligibility_status == "Eligible"],
        key=lambda u: u.user_id,
    )

    if not eligible_users:
        return []

    # Check existing assignments to prevent duplicate baseline assignments
    existing_user_ids = set(
        session.scalars(
            select(Assignment.user_id).where(
                Assignment.experiment_id == experiment_id
            )
        ).all()
    )
    unassigned_users = [
        u for u in eligible_users if u.user_id not in existing_user_ids
    ]
    if not unassigned_users:
        return []

    if override_probabilities is not None:
        if len(override_probabilities) != len(variants):
            raise ValueError(
                "override_probabilities length must match number of variants."
            )
        probs = np.array(override_probabilities, dtype=np.float64)
        probs = probs / probs.sum()
    else:
        probs = np.array(
            [v.allocation_percentage / 100.0 for v in variants], dtype=np.float64
        )
        probs = probs / probs.sum()

    # Derive deterministic experiment-specific RNG stream from (seed, experiment_id)
    exp_num = int(experiment_id.split("-")[-1])
    rng = np.random.default_rng(seed + exp_num * 1009)

    variant_indices = rng.choice(
        len(variants), size=len(unassigned_users), replace=True, p=probs
    )
    minute_offsets = rng.integers(0, 60 * 24 * 5, size=len(unassigned_users))

    start_dt = datetime.fromisoformat(experiment.start_date.replace("Z", "+00:00"))
    assignments: List[Assignment] = []

    for idx, user in enumerate(unassigned_users):
        chosen_variant = variants[int(variant_indices[idx])]
        assigned_dt = start_dt + timedelta(minutes=int(minute_offsets[idx]))
        assigned_iso = assigned_dt.astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        assignment_id = f"ASG-{experiment_id}-{user.user_id}"

        assignments.append(
            Assignment(
                assignment_id=assignment_id,
                experiment_id=experiment_id,
                user_id=user.user_id,
                variant_id=chosen_variant.variant_id,
                assigned_at=assigned_iso,
                assignment_status="Assigned",
                randomization_seed=seed,
            )
        )

    if persist and assignments:
        session.add_all(assignments)
        session.flush()

    return assignments


def validate_randomization_srm(
    session: Session,
    experiment_id: str,
    srm_alpha: float = DEFAULT_SRM_ALPHA,
    record_issue: bool = False,
    detected_at: str = REFERENCE_EPOCH_ISO,
) -> RandomizationValidationResult:
    """Run Chi-square Sample Ratio Mismatch (SRM) test comparing actual vs expected variant counts."""
    variants = list(
        session.scalars(
            select(Variant)
            .where(Variant.experiment_id == experiment_id)
            .order_by(Variant.variant_id.asc())
        ).all()
    )
    validate_experiment_variants(variants)

    # Count baseline assignments per variant
    count_rows = session.execute(
        select(Assignment.variant_id, func.count(Assignment.assignment_id))
        .where(
            Assignment.experiment_id == experiment_id,
            Assignment.assignment_status == "Assigned",
        )
        .group_by(Assignment.variant_id)
    ).all()
    counts_by_variant: Dict[str, int] = {row[0]: int(row[1]) for row in count_rows}

    total_assigned = sum(counts_by_variant.values())
    if total_assigned == 0:
        summaries = [
            VariantAllocationSummary(
                variant_id=v.variant_id,
                variant_name=v.variant_name,
                variant_type=v.variant_type,
                expected_percentage=v.allocation_percentage,
                actual_percentage=0.0,
                expected_count=0.0,
                actual_count=0,
                absolute_percentage_diff=v.allocation_percentage,
            )
            for v in variants
        ]
        return RandomizationValidationResult(
            experiment_id=experiment_id,
            total_assigned=0,
            chi2_statistic=0.0,
            srm_p_value=1.0,
            srm_alpha=srm_alpha,
            srm_detected=False,
            validation_status="INSUFFICIENT_DATA",
            variant_summaries=summaries,
        )

    observed = np.array(
        [counts_by_variant.get(v.variant_id, 0) for v in variants], dtype=np.float64
    )
    expected = np.array(
        [total_assigned * (v.allocation_percentage / 100.0) for v in variants],
        dtype=np.float64,
    )

    chi2_res = chisquare(f_obs=observed, f_exp=expected)
    chi2_stat = float(chi2_res.statistic)
    p_val = float(chi2_res.pvalue)
    srm_detected = bool(p_val < srm_alpha)

    summaries: List[VariantAllocationSummary] = []
    for idx, v in enumerate(variants):
        act_count = int(observed[idx])
        exp_count = float(expected[idx])
        act_pct = (act_count / total_assigned) * 100.0
        abs_diff = abs(act_pct - v.allocation_percentage)
        summaries.append(
            VariantAllocationSummary(
                variant_id=v.variant_id,
                variant_name=v.variant_name,
                variant_type=v.variant_type,
                expected_percentage=v.allocation_percentage,
                actual_percentage=round(act_pct, 6),
                expected_count=round(exp_count, 4),
                actual_count=act_count,
                absolute_percentage_diff=round(abs_diff, 6),
            )
        )

    if srm_detected and record_issue:
        existing_issue = session.scalar(
            select(ExperimentIssue.issue_id).where(
                ExperimentIssue.experiment_id == experiment_id,
                ExperimentIssue.issue_type == "SRM_DETECTED",
            )
        )
        if existing_issue is None:
            issue_count = session.scalar(
                select(func.count(ExperimentIssue.issue_id)).where(
                    ExperimentIssue.experiment_id == experiment_id
                )
            ) or 0
            issue_id = f"ISS-{experiment_id}-{int(issue_count) + 1:04d}"
            exp_ratio_str = ":".join(
                f"{v.allocation_percentage:.1f}%" for v in variants
            )
            act_ratio_str = ":".join(
                f"{s.actual_percentage:.2f}% ({s.actual_count})" for s in summaries
            )
            session.add(
                ExperimentIssue(
                    issue_id=issue_id,
                    experiment_id=experiment_id,
                    affected_entity="experiments",
                    affected_record_id=experiment_id,
                    issue_type="SRM_DETECTED",
                    severity="CRITICAL",
                    detected_at=detected_at,
                    description=(
                        f"Sample Ratio Mismatch detected for {experiment_id}: "
                        f"chi2={chi2_stat:.4f}, p_value={p_val:.6e} < alpha={srm_alpha}."
                    ),
                    expected_behavior=f"Expected allocation split {exp_ratio_str}",
                    actual_behavior=f"Observed allocation split {act_ratio_str}",
                    resolution_status="Open",
                )
            )
            session.flush()

    return RandomizationValidationResult(
        experiment_id=experiment_id,
        total_assigned=total_assigned,
        chi2_statistic=round(chi2_stat, 8),
        srm_p_value=round(p_val, 10),
        srm_alpha=srm_alpha,
        srm_detected=srm_detected,
        validation_status="SRM_FAILED" if srm_detected else "VALID",
        variant_summaries=summaries,
    )