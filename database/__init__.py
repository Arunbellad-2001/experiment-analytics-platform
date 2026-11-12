"""Database package exposing connection utilities and ORM models."""

from database.connection import (
    get_engine,
    get_session_factory,
    init_db,
    session_scope,
    verify_sqlite_version,
)
from database.models import (
    Assignment,
    AudienceMember,
    Base,
    ConversionEvent,
    Experiment,
    ExperimentEvent,
    ExperimentIssue,
    ExperimentResult,
    ExposureEvent,
    GuardrailMetric,
    MetricDefinition,
    Variant,
)

__all__ = [
    "Assignment",
    "AudienceMember",
    "Base",
    "ConversionEvent",
    "Experiment",
    "ExperimentEvent",
    "ExperimentIssue",
    "ExperimentResult",
    "ExposureEvent",
    "GuardrailMetric",
    "MetricDefinition",
    "Variant",
    "get_engine",
    "get_session_factory",
    "init_db",
    "session_scope",
    "verify_sqlite_version",
]