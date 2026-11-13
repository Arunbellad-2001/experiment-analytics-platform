# Database Design

## 1. Authoritative Schema Source of Truth
`database/schema.sql` is the authoritative DDL specification executed during database initialization (`init_db()`). `database/models.py` provides matching SQLAlchemy 2.0 ORM mappings verified for parity in `tests/test_database.py`.

## 2. Operational Tables (11 Entities)
1. `experiments` (`Experiment`): Master experiment metadata, lifecycle status, predeclared `minimum_detectable_effect`, `significance_level`, and `primary_metric_code`.
2. `variants` (`Variant`): Control and Treatment variant definitions with partial unique index `idx_variants_single_control` guaranteeing at most one `Control` variant per experiment.
3. `audience_members` (`AudienceMember`): Synthetic user profiles and eligibility status.
4. `assignments` (`Assignment`): User-to-variant assignments with composite foreign keys to `variants(experiment_id, variant_id)`.
5. `exposure_events` (`ExposureEvent`): Telemetry exposures with composite foreign key to `assignments(assignment_id, experiment_id, user_id, variant_id)`.
6. `conversion_events` (`ConversionEvent`): Purchase and guardrail negative-outcome events with optional composite foreign key to `assignments(assignment_id, experiment_id, user_id)`.
7. `metric_definitions` (`MetricDefinition`): Strictly append-only versioned metric formulas; validity intervals are derived dynamically via `LEAD(effective_from) OVER (PARTITION BY experiment_id, metric_code ORDER BY metric_version ASC)`.
8. `guardrail_metrics` (`GuardrailMetric`): Safety thresholds bound via composite FK to `metric_definitions(metric_id, experiment_id, metric_version)`.
9. `experiment_results` (`ExperimentResult`): Strictly append-only analysis snapshots keyed by `analysis_run_id`, anchored to the verified `Control` variant, and guarded by comparative `CHECK` and `statistical_significance` triggers.
10. `experiment_events` (`ExperimentEvent`): Append-only lifecycle state transition history.
11. `experiment_issues` (`ExperimentIssue`): Detected validation and anomaly issues (zero ground-truth columns).

## 3. Entity Relationship Diagram (ERD)

The following Mermaid diagram displays all 11 operational database entities and their exact foreign-key relationships as defined in `database/schema.sql`:

```mermaid
erDiagram
    experiments ||--o{ variants : "has (experiment_id)"
    experiments ||--o{ assignments : "allocates (experiment_id)"
    experiments ||--o{ exposure_events : "tracks (experiment_id)"
    experiments ||--o{ conversion_events : "monitors (experiment_id)"
    experiments ||--o{ metric_definitions : "defines (experiment_id)"
    experiments ||--o{ guardrail_metrics : "binds (experiment_id)"
    experiments ||--o{ experiment_events : "audits (experiment_id)"
    experiments ||--o{ experiment_issues : "logs (experiment_id)"

    audience_members ||--o{ assignments : "assigned (user_id)"
    audience_members ||--o{ exposure_events : "receives (user_id)"
    audience_members ||--o{ conversion_events : "performs (user_id)"

    variants ||--o{ assignments : "targeted_by (experiment_id, variant_id)"
    variants ||--o{ exposure_events : "exposed_to (experiment_id, variant_id)"
    variants ||--o{ experiment_results : "evaluated (experiment_id, variant_id)"
    variants ||--o{ experiment_results : "anchors_control (experiment_id, control_variant_id)"

    assignments ||--o{ exposure_events : "validates (assignment_id, experiment_id, user_id, variant_id)"
    assignments ||--o{ conversion_events : "attributes (assignment_id, experiment_id, user_id)"

    metric_definitions ||--o{ guardrail_metrics : "governs (metric_id, experiment_id, metric_version)"
    metric_definitions ||--o{ experiment_results : "quantifies (metric_id, experiment_id, metric_version)"

    experiments {
        TEXT experiment_id PK
        TEXT experiment_name
        TEXT description
        TEXT hypothesis
        TEXT primary_metric_code
        REAL minimum_detectable_effect
        REAL significance_level
        TEXT experiment_status
        TEXT expected_allocation_ratio
        TEXT start_date
        TEXT end_date
        INTEGER conversion_window_days
        INTEGER random_seed
        TEXT created_at
        TEXT updated_at
    }

    variants {
        TEXT variant_id PK
        TEXT experiment_id FK
        TEXT variant_name
        TEXT variant_type
        REAL allocation_percentage
        TEXT description
        TEXT created_at
    }

    audience_members {
        TEXT user_id PK
        TEXT user_segment
        TEXT eligibility_status
        TEXT registration_date
        TEXT country_region
        TEXT created_at
    }

    assignments {
        TEXT assignment_id PK
        TEXT experiment_id FK
        TEXT user_id FK
        TEXT variant_id FK
        TEXT assigned_at
        TEXT assignment_status
        INTEGER randomization_seed
    }

    exposure_events {
        TEXT exposure_id PK
        TEXT experiment_id FK
        TEXT assignment_id FK
        TEXT user_id FK
        TEXT variant_id FK
        TEXT exposure_timestamp
        TEXT exposure_status
        TEXT telemetry_status
    }

    conversion_events {
        TEXT conversion_id PK
        TEXT experiment_id FK
        TEXT user_id FK
        TEXT assignment_id FK
        TEXT conversion_type
        TEXT conversion_timestamp
        REAL conversion_value
        TEXT conversion_status
    }

    metric_definitions {
        TEXT metric_id PK
        TEXT experiment_id FK
        TEXT metric_code
        TEXT metric_name
        TEXT metric_type
        TEXT metric_description
        TEXT numerator_definition
        TEXT denominator_definition
        TEXT calculation_method
        INTEGER metric_version
        TEXT effective_from
        TEXT created_at
    }

    guardrail_metrics {
        TEXT guardrail_id PK
        TEXT experiment_id FK
        TEXT metric_id FK
        INTEGER metric_version FK
        TEXT guardrail_name
        TEXT threshold_type
        REAL threshold_value
        TEXT comparison_direction
        TEXT severity
        TEXT created_at
    }

    experiment_results {
        TEXT result_id PK
        TEXT analysis_run_id
        TEXT experiment_id FK
        TEXT variant_id FK
        TEXT control_variant_id FK
        TEXT control_variant_type
        TEXT metric_id FK
        INTEGER metric_version FK
        TEXT analysis_method
        INTEGER sample_size
        REAL numerator
        REAL denominator
        REAL metric_value
        REAL treatment_effect
        REAL relative_lift
        REAL standard_error
        REAL confidence_interval_lower
        REAL confidence_interval_upper
        REAL p_value
        INTEGER statistical_significance
        TEXT guardrail_status
        TEXT decision_status
        TEXT analysis_timestamp
    }

    experiment_events {
        TEXT event_id PK
        TEXT experiment_id FK
        TEXT event_type
        TEXT from_status
        TEXT to_status
        TEXT actor
        TEXT notes
        TEXT event_timestamp
    }

    experiment_issues {
        TEXT issue_id PK
        TEXT experiment_id FK
        TEXT affected_entity
        TEXT affected_record_id
        TEXT issue_type
        TEXT severity
        TEXT detected_at
        TEXT description
        TEXT expected_behavior
        TEXT actual_behavior
        TEXT resolution_status
    }
```

## 4. Referential Integrity, Constraints & Indexes

1. **Foreign Key Enforcement**:
   Every database connection enables SQLite foreign key enforcement using `PRAGMA foreign_keys = ON;`. Composite foreign keys guarantee that downstream entities (`exposure_events`, `conversion_events`, `experiment_results`, `guardrail_metrics`) cannot reference mismatched combinations of `experiment_id`, `variant_id`, or `user_id`.

2. **Partial Unique Index on Control Variants**:
   ```sql
   CREATE UNIQUE INDEX IF NOT EXISTS idx_variants_single_control
   ON variants (experiment_id)
   WHERE variant_type = 'Control';
   ```
   This index enforces at the database storage engine level that an experiment can possess at most one Control variant.

3. **Composite Foreign Keys**:
   - `assignments`: Foreign key to `variants(experiment_id, variant_id)` ensures user assignments match variants belonging to that exact experiment.
   - `exposure_events`: Foreign key to `assignments(assignment_id, experiment_id, user_id, variant_id)` prevents exposure records from cross-pollinating across different user-variant pairings.
   - `conversion_events`: Composite foreign key to `assignments(assignment_id, experiment_id, user_id)` binds conversion attribution strictly to the user's experiment assignment.
   - `guardrail_metrics`: Composite foreign key to `metric_definitions(metric_id, experiment_id, metric_version)` binds guardrails to an exact immutable version of a metric definition.
   - `experiment_results`: Composite foreign keys bind results to `variants(experiment_id, variant_id)`, `variants(experiment_id, control_variant_id, control_variant_type)`, and `metric_definitions(metric_id, experiment_id, metric_version)`.

4. **Domain CHECK Constraints**:
   - `experiments`: `minimum_detectable_effect >= 0.0`, `significance_level > 0.0 AND significance_level < 1.0`, `start_date <= end_date`, `conversion_window_days > 0`.
   - `variants`: `allocation_percentage > 0.0 AND allocation_percentage <= 100.0`.
   - `experiment_results`: Enforces that Control variant baseline rows have `treatment_effect IS NULL`, `p_value IS NULL`, `relative_lift IS NULL`, and `decision_status = 'CONTROL_BASELINE'`, while Treatment rows have non-null `treatment_effect`, `p_value`, `standard_error >= 0.0`, valid confidence intervals (`confidence_interval_lower <= treatment_effect <= confidence_interval_upper`), and `decision_status <> 'CONTROL_BASELINE'`.

## 5. Database Triggers & Immutability Rules

1. **Lifecycle Transition State Machine (`trg_experiments_lifecycle_transitions`)**:
   Blocks illegal state transitions on `experiments.experiment_status`. Only valid forward paths (`Draft -> Ready -> Running <-> Paused -> Completed -> Archived`) are permitted.
2. **Predeclared Parameter Lock (`trg_experiments_lock_predeclared_parameters`)**:
   Prevents updates to `primary_metric_code`, `minimum_detectable_effect`, or `significance_level` once an experiment leaves `Draft` status or once analysis results have been recorded.
3. **Metric Definition Immutability (`trg_metric_definitions_prevent_update`, `trg_metric_definitions_prevent_delete`)**:
   Enforces strictly append-only behavior on `metric_definitions`. Updates and deletes trigger SQLite exceptions; metric changes require inserting a new version (`metric_version + 1`).
4. **Experiment Result Immutability (`trg_experiment_results_prevent_update`, `trg_experiment_results_prevent_delete`)**:
   Ensures analysis snapshots are append-only historical audit records keyed by `analysis_run_id`.
5. **Statistical Significance Verification (`trg_experiment_results_validate_significance`)**:
   Validates on insert that `statistical_significance = 1` if and only if `p_value < experiments.significance_level`.

## 6. Ground-Truth Physical Isolation Principle
The operational SQLite database contains zero ground-truth tables or columns. Ground-truth benchmark labels reside exclusively in external files (`data/ground_truth/ground_truth.csv` and `data/ground_truth/ground_truth.json`). Blind anomaly detection operates solely on operational tables, and ground-truth evaluation is performed by a read-only service that does not alter database state.
