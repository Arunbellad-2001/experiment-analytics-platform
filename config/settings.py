"""Centralized configuration and constants for the Experiment Analytics Platform."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, FrozenSet, Tuple

# ---------------------------------------------------------------------------
# Cross-platform Path Definitions (using pathlib)
# ---------------------------------------------------------------------------
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = BASE_DIR / "data"
STARTER_DATA_DIR: Path = DATA_DIR / "starter"
FULL_DATA_DIR: Path = DATA_DIR / "full"
GROUND_TRUTH_DIR: Path = DATA_DIR / "ground_truth"
LOGS_DIR: Path = BASE_DIR / "logs"
DOC_DIR: Path = BASE_DIR / "documentation"

DEFAULT_DB_PATH: Path = DATA_DIR / "experiment_analytics.db"
SCHEMA_SQL_PATH: Path = BASE_DIR / "database" / "schema.sql"
LOG_FILE_PATH: Path = LOGS_DIR / "platform.log"

# ---------------------------------------------------------------------------
# Reproducibility & Runtime Constants
# ---------------------------------------------------------------------------
DEFAULT_RANDOM_SEED: int = 20261022
GENERATOR_VERSION: str = "1.0.0"
REFERENCE_EPOCH_ISO: str = "2026-01-01T00:00:00Z"
MIN_SQLITE_VERSION: Tuple[int, int, int] = (3, 25, 0)

# Statistical & Validation Defaults
DEFAULT_SIGNIFICANCE_LEVEL: float = 0.05
DEFAULT_SRM_ALPHA: float = 0.001
MIN_GUARDRAIL_DENOMINATOR: int = 30


@dataclass(frozen=True)
class DatasetScaleConfig:
    """Immutable configuration for Starter and Full synthetic dataset generation modes."""

    mode_name: str
    experiment_count: int
    eligible_users_per_experiment: int
    ineligible_users_per_experiment: int
    random_seed: int = DEFAULT_RANDOM_SEED

    @property
    def total_eligible_users(self) -> int:
        return self.experiment_count * self.eligible_users_per_experiment

    @property
    def total_ineligible_users(self) -> int:
        return self.experiment_count * self.ineligible_users_per_experiment

    @property
    def total_audience_members(self) -> int:
        return self.total_eligible_users + self.total_ineligible_users


STARTER_CONFIG = DatasetScaleConfig(
    mode_name="starter",
    experiment_count=5,
    eligible_users_per_experiment=500,
    ineligible_users_per_experiment=50,
    random_seed=DEFAULT_RANDOM_SEED,
)

FULL_CONFIG = DatasetScaleConfig(
    mode_name="full",
    experiment_count=10,
    eligible_users_per_experiment=5000,
    ineligible_users_per_experiment=500,
    random_seed=DEFAULT_RANDOM_SEED,
)

# ---------------------------------------------------------------------------
# Controlled Vocabulary / Enums & Exact Lifecycle State Machine
# ---------------------------------------------------------------------------
ALLOWED_EXPERIMENT_STATUSES: Tuple[str, ...] = (
    "Draft",
    "Ready",
    "Running",
    "Paused",
    "Completed",
    "Archived",
)

ALLOWED_LIFECYCLE_TRANSITIONS: Dict[str, FrozenSet[str]] = {
    "Draft": frozenset({"Ready"}),
    "Ready": frozenset({"Running"}),
    "Running": frozenset({"Paused", "Completed"}),
    "Paused": frozenset({"Running", "Completed"}),
    "Completed": frozenset({"Archived"}),
    "Archived": frozenset(),
}

ALLOWED_VARIANT_TYPES: Tuple[str, ...] = ("Control", "Treatment")
ALLOWED_ELIGIBILITY_STATUSES: Tuple[str, ...] = ("Eligible", "Ineligible")
ALLOWED_ASSIGNMENT_STATUSES: Tuple[str, ...] = ("Assigned", "Duplicate_Anomaly")
ALLOWED_EXPOSURE_STATUSES: Tuple[str, ...] = (
    "Exposed",
    "Failed",
    "Noncompliant",
    "Invalid_Order",
)
ALLOWED_TELEMETRY_STATUSES: Tuple[str, ...] = ("Complete", "Missing", "Delayed")
ALLOWED_CONVERSION_TYPES: Tuple[str, ...] = (
    "Purchase",
    "Refund",
    "Payment_Failure",
    "Complaint",
)
ALLOWED_CONVERSION_STATUSES: Tuple[str, ...] = (
    "Valid",
    "Delayed_In_Window",
    "Outside_Window",
    "Incomplete_Telemetry",
)
ALLOWED_METRIC_TYPES: Tuple[str, ...] = (
    "Primary_Binary",
    "Primary_Continuous",
    "Guardrail_Rate",
)
ALLOWED_METRIC_CALCULATION_METHODS: Tuple[str, ...] = (
    "ITT_Proportion",
    "Exposed_Proportion",
    "ITT_Mean_Value",
)
ALLOWED_THRESHOLD_TYPES: Tuple[str, ...] = (
    "Absolute_Diff",
    "Relative_Lift",
    "Max_Rate",
)
ALLOWED_COMPARISON_DIRECTIONS: Tuple[str, ...] = (
    "MAX_INCREASE",
    "MIN_DECREASE",
    "ABSOLUTE_CAP",
)
ALLOWED_GUARDRAIL_SEVERITIES: Tuple[str, ...] = ("WARNING", "CRITICAL")
ALLOWED_ANALYSIS_METHODS: Tuple[str, ...] = ("ITT", "EXPOSED_SECONDARY")
ALLOWED_GUARDRAIL_STATUSES: Tuple[str, ...] = (
    "PASSED",
    "WARNING",
    "FAILED",
    "INSUFFICIENT_DATA",
    "NOT_APPLICABLE",
)
ALLOWED_DECISION_STATUSES: Tuple[str, ...] = (
    "CONTROL_BASELINE",
    "LAUNCH_TREATMENT",
    "HOLD_FOR_GUARDRAIL_REVIEW",
    "INSUFFICIENT_GUARDRAIL_DATA",
    "DO_NOT_LAUNCH_NO_SIGNIFICANT_LIFT",
    "DO_NOT_LAUNCH_BELOW_MDE",
    "DO_NOT_LAUNCH_GUARDRAIL_BREACH",
    "INVALID_DATA_HOLD",
    "RECALCULATION_REQUIRED",
)
ALLOWED_ISSUE_TYPES: Tuple[str, ...] = (
    "DUPLICATE_ASSIGNMENT",
    "EXPOSURE_BEFORE_ASSIGNMENT",
    "OUTCOME_WINDOW_VIOLATION",
    "SRM_DETECTED",
    "METRIC_VERSION_MISMATCH",
)
ALLOWED_ISSUE_SEVERITIES: Tuple[str, ...] = ("WARNING", "CRITICAL")
ALLOWED_RESOLUTION_STATUSES: Tuple[str, ...] = ("Open", "Acknowledged", "Resolved")


def ensure_directories() -> None:
    """Ensure all required runtime directories exist on any operating system."""
    for directory in (
        DATA_DIR,
        STARTER_DATA_DIR,
        FULL_DATA_DIR,
        GROUND_TRUTH_DIR,
        LOGS_DIR,
        DOC_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure standardized file and console logging."""
    ensure_directories()
    logger = logging.getLogger("experiment_analytics")
    if not logger.handlers:
        logger.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
        file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
        file_handler.setFormatter(formatter)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
    return logger