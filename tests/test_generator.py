"""Automated test suite for Milestone 3: Exposure and Conversion event simulation."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config.settings import STARTER_CONFIG
from database.models import Assignment, ConversionEvent, ExposureEvent
from generator.assignment_generator import generate_assignments_for_all_experiments
from generator.audience_generator import generate_audience_members
from generator.event_generator import simulate_exposures_and_conversions
from generator.master_data import generate_master_data


def test_exposure_and_conversion_simulation_integrity(db_session: Session) -> None:
    """Verify exposures and conversions link to valid parent assignments and model noncompliance/delayed events."""
    generate_master_data(db_session, STARTER_CONFIG)
    pools = generate_audience_members(db_session, STARTER_CONFIG)
    assignments_by_exp = generate_assignments_for_all_experiments(
        db_session, STARTER_CONFIG, pools
    )

    exposures, conversions = simulate_exposures_and_conversions(
        db_session, STARTER_CONFIG, assignments_by_exp
    )

    assert len(exposures) == 2500
    assert len(conversions) > 200
    assert exposures[0].exposure_id == "EXPOS-2026-000001"
    assert conversions[0].conversion_id == "CONV-2026-000001"

    # Verify noncompliance, missing telemetry, and delayed conversions are all represented
    noncompliant_count = db_session.scalar(
        select(func.count(ExposureEvent.exposure_id)).where(
            ExposureEvent.exposure_status == "Noncompliant"
        )
    )
    missing_tel_count = db_session.scalar(
        select(func.count(ExposureEvent.exposure_id)).where(
            ExposureEvent.telemetry_status == "Missing"
        )
    )
    delayed_conv_count = db_session.scalar(
        select(func.count(ConversionEvent.conversion_id)).where(
            ConversionEvent.conversion_status == "Delayed_In_Window"
        )
    )
    assert noncompliant_count and noncompliant_count > 0
    assert missing_tel_count and missing_tel_count > 0
    assert delayed_conv_count and delayed_conv_count > 0

    # Verify every baseline exposure occurs at or after its parent assignment timestamp
    invalid_order_count = db_session.scalar(
        select(func.count(ExposureEvent.exposure_id))
        .join(Assignment, ExposureEvent.assignment_id == Assignment.assignment_id)
        .where(ExposureEvent.exposure_timestamp < Assignment.assigned_at)
    )
    assert invalid_order_count == 0