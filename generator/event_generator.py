"""Steps 6 & 7: ExposureEvent and ConversionEvent simulation engine with noncompliance and telemetry statuses."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.settings import DatasetScaleConfig
from database.models import (
    Assignment,
    ConversionEvent,
    Experiment,
    ExposureEvent,
    Variant,
)
from generator.master_data import get_blueprints_for_config


def simulate_exposures_and_conversions(
    session: Session,
    config: DatasetScaleConfig,
    assignments_by_exp: Dict[str, List[Assignment]],
) -> Tuple[List[ExposureEvent], List[ConversionEvent]]:
    """Simulate realistic exposures (Step 6) and conversions/guardrail events (Step 7) from valid assignments."""
    blueprints = {
        f"EXP-2026-{bp.index:06d}": bp for bp in get_blueprints_for_config(config)
    }

    all_exposures: List[ExposureEvent] = []
    all_conversions: List[ConversionEvent] = []

    exposure_seq = 1
    conversion_seq = 1

    for exp_id in sorted(assignments_by_exp.keys()):
        exp = session.get(Experiment, exp_id)
        if exp is None:
            continue

        bp = blueprints[exp_id]
        assignments = assignments_by_exp[exp_id]
        if not assignments:
            continue

        variants = {
            v.variant_id: v
            for v in session.scalars(
                select(Variant).where(Variant.experiment_id == exp_id)
            ).all()
        }

        exp_num = int(exp_id.split("-")[-1])
        rng = np.random.default_rng(config.random_seed + exp_num * 2027)
        window_minutes = exp.conversion_window_days * 24 * 60

        for asg in assignments:
            variant = variants[asg.variant_id]
            is_treatment = variant.variant_type == "Treatment"
            assigned_dt = datetime.fromisoformat(asg.assigned_at.replace("Z", "+00:00"))

            # -----------------------------------------------------------------
            # Step 6: Exposure Simulation
            # - 88% Exposed (Complete telemetry)
            # - 4% Exposed with Delayed telemetry
            # - 3% Missing telemetry (user exposed, telemetry status Missing)
            # - 3% Noncompliant (user assigned to variant but did not receive experience)
            # - 2% Failed exposure
            # -----------------------------------------------------------------
            exp_roll = float(rng.random())
            delay_mins = int(rng.integers(1, 180))
            exposure_dt = assigned_dt + timedelta(minutes=delay_mins)
            exposure_iso = exposure_dt.astimezone(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

            if exp_roll < 0.88:
                exp_status = "Exposed"
                tel_status = "Complete"
            elif exp_roll < 0.92:
                exp_status = "Exposed"
                tel_status = "Delayed"
            elif exp_roll < 0.95:
                exp_status = "Exposed"
                tel_status = "Missing"
            elif exp_roll < 0.98:
                exp_status = "Noncompliant"
                tel_status = "Complete"
            else:
                exp_status = "Failed"
                tel_status = "Complete"

            all_exposures.append(
                ExposureEvent(
                    exposure_id=f"EXPOS-2026-{exposure_seq:06d}",
                    experiment_id=exp_id,
                    assignment_id=asg.assignment_id,
                    user_id=asg.user_id,
                    variant_id=asg.variant_id,
                    exposure_timestamp=exposure_iso,
                    exposure_status=exp_status,
                    telemetry_status=tel_status,
                )
            )
            exposure_seq += 1

            # -----------------------------------------------------------------
            # Step 7a: Primary Purchase Conversion Simulation
            # Intention-to-treat (ITT) treatment effect applies to exposed compliant users,
            # while noncompliant/failed users convert at reduced baseline rates.
            # -----------------------------------------------------------------
            if exp_status == "Exposed":
                conv_prob = bp.baseline_conversion_rate + (
                    bp.treatment_effect_delta if is_treatment else 0.0
                )
            else:
                conv_prob = bp.baseline_conversion_rate * 0.50

            conv_prob = float(np.clip(conv_prob, 0.001, 0.95))
            if float(rng.random()) < conv_prob:
                # 90% convert well within window (Valid), 10% convert late but inside window (Delayed_In_Window)
                if float(rng.random()) < 0.90:
                    conv_offset_mins = int(
                        rng.integers(delay_mins + 5, max(delay_mins + 60, int(window_minutes * 0.70)))
                    )
                    conv_status = "Valid"
                else:
                    conv_offset_mins = int(
                        rng.integers(
                            int(window_minutes * 0.70),
                            max(int(window_minutes * 0.70) + 10, window_minutes - 10),
                        )
                    )
                    conv_status = "Delayed_In_Window"

                conv_dt = assigned_dt + timedelta(minutes=conv_offset_mins)
                conv_iso = conv_dt.astimezone(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )

                mean_val = bp.baseline_mean_value + (
                    bp.treatment_value_delta if is_treatment else 0.0
                )
                raw_val = float(rng.normal(loc=mean_val, scale=max(5.0, mean_val * 0.15)))
                order_value = round(max(5.0, raw_val), 2)

                all_conversions.append(
                    ConversionEvent(
                        conversion_id=f"CONV-2026-{conversion_seq:06d}",
                        experiment_id=exp_id,
                        user_id=asg.user_id,
                        assignment_id=asg.assignment_id,
                        conversion_type="Purchase",
                        conversion_timestamp=conv_iso,
                        conversion_value=order_value,
                        conversion_status=conv_status,
                    )
                )
                conversion_seq += 1

            # -----------------------------------------------------------------
            # Step 7b: Guardrail Negative-Outcome Events (Refund, Payment_Failure, Complaint)
            # -----------------------------------------------------------------
            refund_prob = (
                bp.refund_rate_treatment if is_treatment else bp.refund_rate_control
            )
            if float(rng.random()) < refund_prob:
                ref_dt = assigned_dt + timedelta(
                    minutes=int(rng.integers(delay_mins + 60, window_minutes - 30))
                )
                all_conversions.append(
                    ConversionEvent(
                        conversion_id=f"CONV-2026-{conversion_seq:06d}",
                        experiment_id=exp_id,
                        user_id=asg.user_id,
                        assignment_id=asg.assignment_id,
                        conversion_type="Refund",
                        conversion_timestamp=ref_dt.astimezone(timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                        conversion_value=0.0,
                        conversion_status="Valid",
                    )
                )
                conversion_seq += 1

            payfail_prob = (
                bp.payment_failure_treatment
                if is_treatment
                else bp.payment_failure_control
            )
            if float(rng.random()) < payfail_prob:
                pf_dt = assigned_dt + timedelta(
                    minutes=int(rng.integers(delay_mins + 10, window_minutes - 60))
                )
                all_conversions.append(
                    ConversionEvent(
                        conversion_id=f"CONV-2026-{conversion_seq:06d}",
                        experiment_id=exp_id,
                        user_id=asg.user_id,
                        assignment_id=asg.assignment_id,
                        conversion_type="Payment_Failure",
                        conversion_timestamp=pf_dt.astimezone(timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                        conversion_value=0.0,
                        conversion_status="Valid",
                    )
                )
                conversion_seq += 1

            complaint_prob = (
                bp.complaint_rate_treatment
                if is_treatment
                else bp.complaint_rate_control
            )
            if float(rng.random()) < complaint_prob:
                cmp_dt = assigned_dt + timedelta(
                    minutes=int(rng.integers(delay_mins + 120, window_minutes - 30))
                )
                all_conversions.append(
                    ConversionEvent(
                        conversion_id=f"CONV-2026-{conversion_seq:06d}",
                        experiment_id=exp_id,
                        user_id=asg.user_id,
                        assignment_id=asg.assignment_id,
                        conversion_type="Complaint",
                        conversion_timestamp=cmp_dt.astimezone(timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                        conversion_value=0.0,
                        conversion_status="Valid",
                    )
                )
                conversion_seq += 1

    session.add_all(all_exposures)
    session.add_all(all_conversions)
    session.flush()
    return all_exposures, all_conversions