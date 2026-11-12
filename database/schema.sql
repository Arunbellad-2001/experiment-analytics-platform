-- ============================================================================
-- Experiment Analytics Platform - Authoritative SQLite Relational Schema
-- ============================================================================
-- Enforces:
-- 1. All 9 core entities + 2 operational supporting entities (11 tables total).
--    Ground-truth records are isolated strictly to external files.
-- 2. Composite foreign keys ensuring cross-table experiment/user/variant alignment.
-- 3. Partial unique index ensuring at most one Control variant per experiment.
-- 4. Strict lifecycle state machine & predeclared parameter locks.
-- 5. Append-only immutability on metric_definitions and experiment_results.
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------------------------
-- Entity 1: Experiment (experiments)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS experiments (
    experiment_id TEXT PRIMARY KEY,
    experiment_name TEXT NOT NULL,
    description TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    primary_metric_code TEXT NOT NULL,
    minimum_detectable_effect REAL NOT NULL CHECK (minimum_detectable_effect >= 0.0),
    significance_level REAL NOT NULL DEFAULT 0.05 CHECK (significance_level > 0.0 AND significance_level < 1.0),
    experiment_status TEXT NOT NULL CHECK (
        experiment_status IN ('Draft', 'Ready', 'Running', 'Paused', 'Completed', 'Archived')
    ),
    expected_allocation_ratio TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    conversion_window_days INTEGER NOT NULL CHECK (conversion_window_days > 0),
    random_seed INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (start_date <= end_date)
);

CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments (experiment_status);

-- ----------------------------------------------------------------------------
-- Entity 2: Variant (variants)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS variants (
    variant_id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    variant_name TEXT NOT NULL,
    variant_type TEXT NOT NULL CHECK (variant_type IN ('Control', 'Treatment')),
    allocation_percentage REAL NOT NULL CHECK (
        allocation_percentage > 0.0 AND allocation_percentage <= 100.0
    ),
    description TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiments (experiment_id),
    UNIQUE (experiment_id, variant_name),
    UNIQUE (experiment_id, variant_id),
    UNIQUE (experiment_id, variant_id, variant_type)
);

-- Guarantees at most ONE Control variant per experiment at the SQLite level
CREATE UNIQUE INDEX IF NOT EXISTS idx_variants_single_control
ON variants (experiment_id)
WHERE variant_type = 'Control';

CREATE INDEX IF NOT EXISTS idx_variants_experiment ON variants (experiment_id);

-- ----------------------------------------------------------------------------
-- Entity 3: AudienceMember (audience_members)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audience_members (
    user_id TEXT PRIMARY KEY,
    user_segment TEXT NOT NULL,
    eligibility_status TEXT NOT NULL CHECK (eligibility_status IN ('Eligible', 'Ineligible')),
    registration_date TEXT NOT NULL,
    country_region TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audience_eligibility ON audience_members (eligibility_status);
CREATE INDEX IF NOT EXISTS idx_audience_segment ON audience_members (user_segment);

-- ----------------------------------------------------------------------------
-- Entity 4: Assignment (assignments)
-- Note: (experiment_id, user_id) uses a non-unique composite index so baseline
-- generation enforces 1 assignment per user in application logic while allowing
-- deliberate duplicate-assignment anomalies (Edge Case 1) to be persisted and detected.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS assignments (
    assignment_id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    variant_id TEXT NOT NULL,
    assigned_at TEXT NOT NULL,
    assignment_status TEXT NOT NULL CHECK (
        assignment_status IN ('Assigned', 'Duplicate_Anomaly')
    ),
    randomization_seed INTEGER NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiments (experiment_id),
    FOREIGN KEY (user_id) REFERENCES audience_members (user_id),
    FOREIGN KEY (experiment_id, variant_id) REFERENCES variants (experiment_id, variant_id),
    UNIQUE (assignment_id, experiment_id, user_id, variant_id),
    UNIQUE (assignment_id, experiment_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_assignments_exp_user ON assignments (experiment_id, user_id);
CREATE INDEX IF NOT EXISTS idx_assignments_exp_variant ON assignments (experiment_id, variant_id);

-- ----------------------------------------------------------------------------
-- Entity 5: ExposureEvent (exposure_events)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exposure_events (
    exposure_id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    assignment_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    variant_id TEXT NOT NULL,
    exposure_timestamp TEXT NOT NULL,
    exposure_status TEXT NOT NULL CHECK (
        exposure_status IN ('Exposed', 'Failed', 'Noncompliant', 'Invalid_Order')
    ),
    telemetry_status TEXT NOT NULL CHECK (
        telemetry_status IN ('Complete', 'Missing', 'Delayed')
    ),
    FOREIGN KEY (experiment_id) REFERENCES experiments (experiment_id),
    FOREIGN KEY (user_id) REFERENCES audience_members (user_id),
    FOREIGN KEY (experiment_id, variant_id) REFERENCES variants (experiment_id, variant_id),
    FOREIGN KEY (assignment_id, experiment_id, user_id, variant_id)
        REFERENCES assignments (assignment_id, experiment_id, user_id, variant_id)
);

CREATE INDEX IF NOT EXISTS idx_exposures_exp_variant ON exposure_events (experiment_id, variant_id);
CREATE INDEX IF NOT EXISTS idx_exposures_assignment ON exposure_events (assignment_id);

-- ----------------------------------------------------------------------------
-- Entity 6: ConversionEvent (conversion_events)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversion_events (
    conversion_id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    assignment_id TEXT NULL,
    conversion_type TEXT NOT NULL CHECK (
        conversion_type IN ('Purchase', 'Refund', 'Payment_Failure', 'Complaint')
    ),
    conversion_timestamp TEXT NOT NULL,
    conversion_value REAL NOT NULL DEFAULT 0.0,
    conversion_status TEXT NOT NULL CHECK (
        conversion_status IN ('Valid', 'Delayed_In_Window', 'Outside_Window', 'Incomplete_Telemetry')
    ),
    FOREIGN KEY (experiment_id) REFERENCES experiments (experiment_id),
    FOREIGN KEY (user_id) REFERENCES audience_members (user_id),
    FOREIGN KEY (assignment_id, experiment_id, user_id)
        REFERENCES assignments (assignment_id, experiment_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_conversions_exp_user ON conversion_events (experiment_id, user_id);
CREATE INDEX IF NOT EXISTS idx_conversions_exp_type ON conversion_events (experiment_id, conversion_type);

-- ----------------------------------------------------------------------------
-- Entity 7: MetricDefinition (metric_definitions)
-- Strictly append-only. Validity window derived dynamically via LEAD(effective_from).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metric_definitions (
    metric_id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    metric_code TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_type TEXT NOT NULL CHECK (
        metric_type IN ('Primary_Binary', 'Primary_Continuous', 'Guardrail_Rate')
    ),
    metric_description TEXT NOT NULL,
    numerator_definition TEXT NOT NULL,
    denominator_definition TEXT NOT NULL,
    calculation_method TEXT NOT NULL CHECK (
        calculation_method IN ('ITT_Proportion', 'Exposed_Proportion', 'ITT_Mean_Value')
    ),
    metric_version INTEGER NOT NULL CHECK (metric_version >= 1),
    effective_from TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiments (experiment_id),
    UNIQUE (experiment_id, metric_code, metric_version),
    UNIQUE (metric_id, experiment_id, metric_version)
);

CREATE INDEX IF NOT EXISTS idx_metrics_exp_code_ver
ON metric_definitions (experiment_id, metric_code, metric_version);

-- ----------------------------------------------------------------------------
-- Entity 8: GuardrailMetric (guardrail_metrics)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS guardrail_metrics (
    guardrail_id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    metric_id TEXT NOT NULL,
    metric_version INTEGER NOT NULL,
    guardrail_name TEXT NOT NULL,
    threshold_type TEXT NOT NULL CHECK (
        threshold_type IN ('Absolute_Diff', 'Relative_Lift', 'Max_Rate')
    ),
    threshold_value REAL NOT NULL,
    comparison_direction TEXT NOT NULL CHECK (
        comparison_direction IN ('MAX_INCREASE', 'MIN_DECREASE', 'ABSOLUTE_CAP')
    ),
    severity TEXT NOT NULL CHECK (severity IN ('WARNING', 'CRITICAL')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiments (experiment_id),
    FOREIGN KEY (metric_id, experiment_id, metric_version)
        REFERENCES metric_definitions (metric_id, experiment_id, metric_version)
);

CREATE INDEX IF NOT EXISTS idx_guardrails_experiment ON guardrail_metrics (experiment_id);

-- ----------------------------------------------------------------------------
-- Entity 9: ExperimentResult (experiment_results)
-- Strictly append-only. Grain includes analysis_run_id and control-anchored checks.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS experiment_results (
    result_id TEXT PRIMARY KEY,
    analysis_run_id TEXT NOT NULL,
    experiment_id TEXT NOT NULL,
    variant_id TEXT NOT NULL,
    control_variant_id TEXT NOT NULL,
    control_variant_type TEXT NOT NULL DEFAULT 'Control' CHECK (control_variant_type = 'Control'),
    metric_id TEXT NOT NULL,
    metric_version INTEGER NOT NULL,
    analysis_method TEXT NOT NULL CHECK (analysis_method IN ('ITT', 'EXPOSED_SECONDARY')),
    sample_size INTEGER NOT NULL CHECK (sample_size >= 0),
    numerator REAL NOT NULL,
    denominator REAL NOT NULL CHECK (denominator >= 0.0),
    metric_value REAL NOT NULL,
    treatment_effect REAL NULL,
    relative_lift REAL NULL,
    standard_error REAL NULL CHECK (standard_error IS NULL OR standard_error >= 0.0),
    confidence_interval_lower REAL NULL,
    confidence_interval_upper REAL NULL,
    p_value REAL NULL CHECK (p_value IS NULL OR (p_value >= 0.0 AND p_value <= 1.0)),
    statistical_significance INTEGER NULL CHECK (
        statistical_significance IS NULL OR statistical_significance IN (0, 1)
    ),
    guardrail_status TEXT NOT NULL CHECK (
        guardrail_status IN ('PASSED', 'WARNING', 'FAILED', 'INSUFFICIENT_DATA', 'NOT_APPLICABLE')
    ),
    decision_status TEXT NOT NULL CHECK (
        decision_status IN (
            'CONTROL_BASELINE',
            'LAUNCH_TREATMENT',
            'HOLD_FOR_GUARDRAIL_REVIEW',
            'INSUFFICIENT_GUARDRAIL_DATA',
            'DO_NOT_LAUNCH_NO_SIGNIFICANT_LIFT',
            'DO_NOT_LAUNCH_BELOW_MDE',
            'DO_NOT_LAUNCH_GUARDRAIL_BREACH',
            'INVALID_DATA_HOLD',
            'RECALCULATION_REQUIRED'
        )
    ),
    analysis_timestamp TEXT NOT NULL,
    FOREIGN KEY (experiment_id, variant_id) REFERENCES variants (experiment_id, variant_id),
    FOREIGN KEY (experiment_id, control_variant_id, control_variant_type)
        REFERENCES variants (experiment_id, variant_id, variant_type),
    FOREIGN KEY (metric_id, experiment_id, metric_version)
        REFERENCES metric_definitions (metric_id, experiment_id, metric_version),
    UNIQUE (analysis_run_id, experiment_id, variant_id, metric_id, metric_version, analysis_method),
    CHECK (
        (
            variant_id = control_variant_id
            AND treatment_effect IS NULL
            AND relative_lift IS NULL
            AND standard_error IS NULL
            AND confidence_interval_lower IS NULL
            AND confidence_interval_upper IS NULL
            AND p_value IS NULL
            AND statistical_significance IS NULL
            AND decision_status = 'CONTROL_BASELINE'
        )
        OR
        (
            variant_id <> control_variant_id
            AND treatment_effect IS NOT NULL
            AND (denominator = 0.0 OR relative_lift IS NOT NULL)
            AND standard_error IS NOT NULL
            AND standard_error >= 0.0
            AND confidence_interval_lower IS NOT NULL
            AND confidence_interval_upper IS NOT NULL
            AND confidence_interval_lower <= treatment_effect
            AND treatment_effect <= confidence_interval_upper
            AND p_value IS NOT NULL
            AND p_value >= 0.0
            AND p_value <= 1.0
            AND statistical_significance IS NOT NULL
            AND decision_status <> 'CONTROL_BASELINE'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_results_exp_run ON experiment_results (experiment_id, analysis_run_id);

-- ----------------------------------------------------------------------------
-- Supporting Entity 10: ExperimentEvent (experiment_events)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS experiment_events (
    event_id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    from_status TEXT NULL,
    to_status TEXT NOT NULL,
    actor TEXT NOT NULL,
    notes TEXT NOT NULL,
    event_timestamp TEXT NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiments (experiment_id)
);

CREATE INDEX IF NOT EXISTS idx_events_experiment ON experiment_events (experiment_id);

-- ----------------------------------------------------------------------------
-- Supporting Entity 11: ExperimentIssue (experiment_issues)
-- Strictly operational; zero ground-truth fields.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS experiment_issues (
    issue_id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    affected_entity TEXT NOT NULL,
    affected_record_id TEXT NOT NULL,
    issue_type TEXT NOT NULL CHECK (
        issue_type IN (
            'DUPLICATE_ASSIGNMENT',
            'EXPOSURE_BEFORE_ASSIGNMENT',
            'OUTCOME_WINDOW_VIOLATION',
            'SRM_DETECTED',
            'METRIC_VERSION_MISMATCH'
        )
    ),
    severity TEXT NOT NULL CHECK (severity IN ('WARNING', 'CRITICAL')),
    detected_at TEXT NOT NULL,
    description TEXT NOT NULL,
    expected_behavior TEXT NOT NULL,
    actual_behavior TEXT NOT NULL,
    resolution_status TEXT NOT NULL CHECK (
        resolution_status IN ('Open', 'Acknowledged', 'Resolved')
    ),
    FOREIGN KEY (experiment_id) REFERENCES experiments (experiment_id)
);

CREATE INDEX IF NOT EXISTS idx_issues_exp_type ON experiment_issues (experiment_id, issue_type);

-- ============================================================================
-- Database Triggers for Lifecycle, Immutability & Domain Consistency
-- ============================================================================

-- 1. Strict Lifecycle Transitions Trigger
CREATE TRIGGER IF NOT EXISTS trg_experiments_lifecycle_transitions
BEFORE UPDATE OF experiment_status ON experiments
WHEN NEW.experiment_status IS NOT OLD.experiment_status
BEGIN
    SELECT CASE
        WHEN OLD.experiment_status <> 'Draft' AND NEW.experiment_status = 'Draft' THEN
            RAISE(ABORT, 'Invalid lifecycle transition: an experiment cannot return to Draft after leaving Draft status')
        WHEN OLD.experiment_status = 'Archived' THEN
            RAISE(ABORT, 'Invalid lifecycle transition: Archived is a terminal state and allows no further transitions')
        WHEN NOT (
            (OLD.experiment_status = 'Draft' AND NEW.experiment_status = 'Ready')
            OR (OLD.experiment_status = 'Ready' AND NEW.experiment_status = 'Running')
            OR (OLD.experiment_status = 'Running' AND NEW.experiment_status IN ('Paused', 'Completed'))
            OR (OLD.experiment_status = 'Paused' AND NEW.experiment_status IN ('Running', 'Completed'))
            OR (OLD.experiment_status = 'Completed' AND NEW.experiment_status = 'Archived')
        ) THEN
            RAISE(ABORT, 'Invalid experiment_status lifecycle transition')
    END;
END;

-- 2. Lock Predeclared Parameters Trigger
CREATE TRIGGER IF NOT EXISTS trg_experiments_lock_predeclared_parameters
BEFORE UPDATE ON experiments
WHEN (
    NEW.minimum_detectable_effect IS NOT OLD.minimum_detectable_effect
    OR NEW.significance_level IS NOT OLD.significance_level
    OR NEW.primary_metric_code IS NOT OLD.primary_metric_code
)
BEGIN
    SELECT CASE
        WHEN OLD.experiment_status <> 'Draft' OR NEW.experiment_status <> 'Draft' THEN
            RAISE(ABORT, 'Predeclared parameters (minimum_detectable_effect, significance_level, primary_metric_code) can only be modified while experiment_status remains in Draft')
        WHEN EXISTS (
            SELECT 1 FROM experiment_results WHERE experiment_id = OLD.experiment_id
        ) THEN
            RAISE(ABORT, 'Predeclared parameters cannot be modified after analysis results have been recorded')
    END;
END;

-- 3. Primary Metric Type & MDE Scale Validation on experiments update
CREATE TRIGGER IF NOT EXISTS trg_experiments_validate_primary_metric_and_mde
BEFORE UPDATE ON experiments
BEGIN
    SELECT CASE
        WHEN EXISTS (
            SELECT 1 FROM metric_definitions
            WHERE experiment_id = NEW.experiment_id
              AND metric_code = NEW.primary_metric_code
              AND metric_type = 'Guardrail_Rate'
        ) THEN
            RAISE(ABORT, 'Invalid primary_metric_code: Guardrail_Rate metric cannot be used as an experiment primary metric')
        WHEN NEW.minimum_detectable_effect > 1.0 AND EXISTS (
            SELECT 1 FROM metric_definitions
            WHERE experiment_id = NEW.experiment_id
              AND metric_code = NEW.primary_metric_code
              AND metric_type = 'Primary_Binary'
        ) THEN
            RAISE(ABORT, 'Invalid minimum_detectable_effect: Primary_Binary metrics require 0.0 <= minimum_detectable_effect <= 1.0')
        WHEN NEW.experiment_status <> 'Draft' AND NOT EXISTS (
            SELECT 1 FROM metric_definitions
            WHERE experiment_id = NEW.experiment_id
              AND metric_code = NEW.primary_metric_code
              AND metric_type IN ('Primary_Binary', 'Primary_Continuous')
        ) THEN
            RAISE(ABORT, 'Cannot transition experiment out of Draft: primary_metric_code must reference an existing Primary_Binary or Primary_Continuous metric definition')
    END;
END;

-- 4. Validate Primary Metric Type & Binary MDE on metric_definitions insert
CREATE TRIGGER IF NOT EXISTS trg_metric_definitions_validate_primary_and_mde
BEFORE INSERT ON metric_definitions
BEGIN
    SELECT CASE
        WHEN NEW.metric_type = 'Guardrail_Rate' AND EXISTS (
            SELECT 1 FROM experiments
            WHERE experiment_id = NEW.experiment_id
              AND primary_metric_code = NEW.metric_code
        ) THEN
            RAISE(ABORT, 'Invalid metric_type: experiment primary_metric_code must be Primary_Binary or Primary_Continuous, not Guardrail_Rate')
        WHEN NEW.metric_type = 'Primary_Binary' AND EXISTS (
            SELECT 1 FROM experiments
            WHERE experiment_id = NEW.experiment_id
              AND primary_metric_code = NEW.metric_code
              AND (minimum_detectable_effect < 0.0 OR minimum_detectable_effect > 1.0)
        ) THEN
            RAISE(ABORT, 'Invalid minimum_detectable_effect on parent experiment: Primary_Binary metrics require 0.0 <= minimum_detectable_effect <= 1.0')
    END;
END;

-- 5. Enforce Monotonic Metric Version Sequence & Effective Dates
CREATE TRIGGER IF NOT EXISTS trg_metric_definitions_version_sequence
BEFORE INSERT ON metric_definitions
BEGIN
    SELECT CASE
        WHEN NEW.metric_version = 1 AND EXISTS (
            SELECT 1 FROM metric_definitions
            WHERE experiment_id = NEW.experiment_id
              AND metric_code = NEW.metric_code
        ) THEN
            RAISE(ABORT, 'metric_version 1 already exists for this experiment_id and metric_code')
        WHEN NEW.metric_version > 1 AND NOT EXISTS (
            SELECT 1 FROM metric_definitions
            WHERE experiment_id = NEW.experiment_id
              AND metric_code = NEW.metric_code
              AND metric_version = NEW.metric_version - 1
              AND effective_from < NEW.effective_from
        ) THEN
            RAISE(ABORT, 'New metric_version must increment prior version by 1 and have a strictly later effective_from timestamp')
    END;
END;

-- 6. Strict Append-Only Immutability on metric_definitions
CREATE TRIGGER IF NOT EXISTS trg_metric_definitions_no_update
BEFORE UPDATE ON metric_definitions
BEGIN
    SELECT RAISE(ABORT, 'metric_definitions is strictly append-only and immutable');
END;

CREATE TRIGGER IF NOT EXISTS trg_metric_definitions_no_delete
BEFORE DELETE ON metric_definitions
BEGIN
    SELECT RAISE(ABORT, 'metric_definitions is strictly append-only and immutable');
END;

-- 7. Stored statistical_significance Consistency on experiment_results
CREATE TRIGGER IF NOT EXISTS trg_experiment_results_validate_significance
BEFORE INSERT ON experiment_results
WHEN NEW.variant_id <> NEW.control_variant_id
BEGIN
    SELECT CASE
        WHEN NEW.p_value < (
            SELECT significance_level FROM experiments WHERE experiment_id = NEW.experiment_id
        ) AND NEW.statistical_significance <> 1 THEN
            RAISE(ABORT, 'Inconsistent statistical_significance: must be 1 when p_value < experiments.significance_level')
        WHEN NEW.p_value >= (
            SELECT significance_level FROM experiments WHERE experiment_id = NEW.experiment_id
        ) AND NEW.statistical_significance <> 0 THEN
            RAISE(ABORT, 'Inconsistent statistical_significance: must be 0 when p_value >= experiments.significance_level')
    END;
END;

-- 8. Strict Append-Only Immutability on experiment_results
CREATE TRIGGER IF NOT EXISTS trg_experiment_results_no_update
BEFORE UPDATE ON experiment_results
BEGIN
    SELECT RAISE(ABORT, 'experiment_results is strictly append-only and immutable');
END;

CREATE TRIGGER IF NOT EXISTS trg_experiment_results_no_delete
BEFORE DELETE ON experiment_results
BEGIN
    SELECT RAISE(ABORT, 'experiment_results is strictly append-only and immutable');
END;