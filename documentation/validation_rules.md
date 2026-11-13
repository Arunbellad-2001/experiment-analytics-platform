# Validation Rules & Negative Edge Cases

## 1. Database & Structural Validation Rules
1. **Primary & Composite Foreign Keys**:
   - `PRAGMA foreign_keys = ON` is enforced on every SQLite connection.
   - `assignments(experiment_id, variant_id)` references `variants(experiment_id, variant_id)`.
   - `exposure_events(assignment_id, experiment_id, user_id, variant_id)` references `assignments(assignment_id, experiment_id, user_id, variant_id)`.
   - `conversion_events(assignment_id, experiment_id, user_id)` references `assignments(assignment_id, experiment_id, user_id)` when `assignment_id IS NOT NULL`.
   - `experiment_results(experiment_id, control_variant_id, control_variant_type)` references `variants(experiment_id, variant_id, variant_type)` with `CHECK (control_variant_type = 'Control')`.
2. **Single Control Variant Enforcement**:
   - Partial unique index `idx_variants_single_control ON variants(experiment_id) WHERE variant_type = 'Control'` guarantees at most one Control variant per experiment in SQLite, paired with service validation requiring exactly one Control variant.
3. **Append-Only Historical Immutability**:
   - `metric_definitions` and `experiment_results` are guarded by `BEFORE UPDATE` and `BEFORE DELETE` triggers that abort any mutation or deletion.

## 2. Five Required Negative Anomaly Scenarios
| Scenario ID | Edge Case | Issue Type | Severity | Detection Rule (`services/anomaly_detection.py`) | Expected Decision Impact |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `GT-2026-0001` | User assigned to multiple variants | `DUPLICATE_ASSIGNMENT` | `CRITICAL` | `GROUP BY experiment_id, user_id HAVING COUNT(DISTINCT variant_id) > 1` | `INVALID_DATA_HOLD` |
| `GT-2026-0002` | Exposure before assignment | `EXPOSURE_BEFORE_ASSIGNMENT` | `CRITICAL` | `exposure_events.exposure_timestamp < assignments.assigned_at` | `INVALID_DATA_HOLD` |
| `GT-2026-0003` | Conversion outside outcome window | `OUTCOME_WINDOW_VIOLATION` | `CRITICAL` | `conversion_timestamp > assigned_at + conversion_window_days` or `< assigned_at` | `INVALID_DATA_HOLD` (excluded from valid metric numerators) |
| `GT-2026-0004` | Sample ratio mismatch ignored | `SRM_DETECTED` | `CRITICAL` | Chi-square test `p_SRM < 0.001` between observed and expected variant counts | `INVALID_DATA_HOLD` |
| `GT-2026-0005` | Metric definition changes after results | `METRIC_VERSION_MISMATCH` | `WARNING` | `MAX(metric_definitions.metric_version) > MAX(experiment_results.metric_version)` for primary metric | `RECALCULATION_REQUIRED` |