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