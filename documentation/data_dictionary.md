# Data Dictionary

## 1. `experiments`
| Field Name | Data Type | Required | Allowed Values | Unit | Uniqueness | Validation Rule | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `experiment_id` | TEXT | Required | `EXP-2026-XXXXXX` | ID | Primary Key | Non-empty unique ID | Unique experiment identifier |
| `experiment_name` | TEXT | Required | Non-empty text | Text | Non-unique | Not null | Human-readable experiment title |
| `description` | TEXT | Required | Non-empty text | Text | Non-unique | Not null | Detailed context of the experiment |
| `hypothesis` | TEXT | Required | Non-empty text | Text | Non-unique | Not null | Testable falsifiable hypothesis |
| `primary_metric_code` | TEXT | Required | `MET-EXP-...` | Code | Non-unique | Locked after `Draft`; must reference `Primary_Binary` or `Primary_Continuous` | Sole authoritative pointer to primary metric |
| `minimum_detectable_effect` | REAL | Required | `[0.0, 1.0]` (binary) or `>= 0.0` (continuous) | Proportion diff / native unit | Non-unique | Locked after `Draft` or once results exist | Predeclared practical significance threshold |
| `significance_level` | REAL | Required | `(0.0, 1.0)` (default `0.05`) | Probability | Non-unique | Locked after `Draft` or once results exist | Predeclared two-sided Type I error rate |
| `experiment_status` | TEXT | Required | `Draft`, `Ready`, `Running`, `Paused`, `Completed`, `Archived` | Enum | Non-unique | Strict forward state machine trigger | Current lifecycle state |
| `expected_allocation_ratio` | TEXT | Required | e.g., `50:50`, `80:20` | Ratio | Non-unique | Matches variant allocation percentages | Target variant traffic split |
| `start_date` | TEXT | Required | ISO-8601 UTC | UTC Timestamp | Non-unique | `start_date <= end_date` | Experiment start timestamp |
| `end_date` | TEXT | Required | ISO-8601 UTC | UTC Timestamp | Non-unique | `start_date <= end_date` | Experiment end timestamp |
| `conversion_window_days` | INTEGER | Required | `> 0` | Days | Non-unique | Positive integer | Maximum days post-assignment for valid conversion |
| `random_seed` | INTEGER | Required | Integer (default `20261022`) | Seed | Non-unique | Deterministic integer | PRNG seed for reproducibility |
| `created_at` | TEXT | Required | ISO-8601 UTC | UTC Timestamp | Non-unique | Valid UTC string | Creation timestamp |
| `updated_at` | TEXT | Required | ISO-8601 UTC | UTC Timestamp | Non-unique | Valid UTC string | Last update timestamp |

## 2. `variants`
| Field Name | Data Type | Required | Allowed Values | Unit | Uniqueness | Validation Rule | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `variant_id` | TEXT | Required | `VAR-EXP-2026-XXXXXX-A` | ID | PK; `UNIQUE(experiment_id, variant_id)` | Non-empty | Unique variant identifier |
| `experiment_id` | TEXT | Required | Valid `experiment_id` | ID | FK | References `experiments` | Parent experiment ID |
| `variant_name` | TEXT | Required | e.g., `A`, `B` | Text | `UNIQUE(experiment_id, variant_name)` | Not null | Short variant label |
| `variant_type` | TEXT | Required | `Control`, `Treatment` | Enum | Partial unique index for `Control` per `experiment_id` | Exactly one `Control` per experiment | Role of the variant |
| `allocation_percentage` | REAL | Required | `(0.0, 100.0]` | Percentage | Non-unique | Sum across experiment variants = `100.0` | Target traffic share |
| `description` | TEXT | Required | Non-empty text | Text | Non-unique | Not null | Variant experience description |
| `created_at` | TEXT | Required | ISO-8601 UTC | UTC Timestamp | Non-unique | Valid UTC string | Creation timestamp |

## 3. `audience_members`
| Field Name | Data Type | Required | Allowed Values | Unit | Uniqueness | Validation Rule | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `user_id` | TEXT | Required | `USER-XXXXXX` | ID | Primary Key | Synthetic ID only | Unique synthetic user ID |
| `user_segment` | TEXT | Required | `New`, `Returning`, `Enterprise`, `SMB` | Enum | Non-unique | Not null | Customer behavioral segment |
| `eligibility_status` | TEXT | Required | `Eligible`, `Ineligible` | Enum | Non-unique | Only `Eligible` assigned in baseline | Experiment eligibility flag |
| `registration_date` | TEXT | Required | ISO-8601 UTC | UTC Timestamp | Non-unique | Valid UTC string | Synthetic registration timestamp |
| `country_region` | TEXT | Required | `US-East`, `EU-West`, `APAC-South`, `LATAM` | Region | Non-unique | Synthetic region code | Synthetic geographic bucket |
| `created_at` | TEXT | Required | ISO-8601 UTC | UTC Timestamp | Non-unique | Valid UTC string | Record creation timestamp |

## 4. `assignments`
| Field Name | Data Type | Required | Allowed Values | Unit | Uniqueness | Validation Rule | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `assignment_id` | TEXT | Required | `ASG-EXP-...-USER-...` | ID | Primary Key | Deterministic ID | Unique assignment identifier |
| `experiment_id` | TEXT | Required | Valid `experiment_id` | ID | Composite FK | Must match variant's experiment | Parent experiment ID |
| `user_id` | TEXT | Required | Valid `user_id` | ID | FK | Must be `Eligible` in baseline | Assigned audience member ID |
| `variant_id` | TEXT | Required | Valid `variant_id` | ID | Composite FK `(experiment_id, variant_id)` | Must belong to `experiment_id` | Assigned variant ID |
| `assigned_at` | TEXT | Required | ISO-8601 UTC | UTC Timestamp | Non-unique | Within experiment window | Assignment timestamp |
| `assignment_status` | TEXT | Required | `Assigned`, `Duplicate_Anomaly` | Enum | Non-unique | Checked enum | Status of assignment |
| `randomization_seed` | INTEGER | Required | Integer | Seed | Non-unique | Matches deterministic generator | Seed used for randomization |

## 5. `exposure_events`
| Field Name | Data Type | Required | Allowed Values | Unit | Uniqueness | Validation Rule | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `exposure_id` | TEXT | Required | `EXPOS-2026-XXXXXX` | ID | Primary Key | Deterministic ID | Unique exposure event ID |
| `experiment_id` | TEXT | Required | Valid `experiment_id` | ID | Composite FK | Matches assignment's experiment | Parent experiment ID |
| `assignment_id` | TEXT | Required | Valid `assignment_id` | ID | Composite FK `(assignment_id, experiment_id, user_id, variant_id)` | Must match parent assignment | Referenced assignment ID |
| `user_id` | TEXT | Required | Valid `user_id` | ID | Composite FK | Matches assignment's user | Exposed user ID |
| `variant_id` | TEXT | Required | Valid `variant_id` | ID | Composite FK | Matches assignment's variant | Exposed variant ID |
| `exposure_timestamp` | TEXT | Required | ISO-8601 UTC | UTC Timestamp | Non-unique | `>= assigned_at` in valid baseline | Exposure timestamp |
| `exposure_status` | TEXT | Required | `Exposed`, `Failed`, `Noncompliant`, `Invalid_Order` | Enum | Non-unique | Checked enum | Outcome of exposure attempt |
| `telemetry_status` | TEXT | Required | `Complete`, `Missing`, `Delayed` | Enum | Non-unique | Checked enum | Telemetry capture state |

## 6. `conversion_events`
| Field Name | Data Type | Required | Allowed Values | Unit | Uniqueness | Validation Rule | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `conversion_id` | TEXT | Required | `CONV-2026-XXXXXX` | ID | Primary Key | Deterministic ID | Unique conversion event ID |
| `experiment_id` | TEXT | Required | Valid `experiment_id` | ID | Composite FK | Matches assignment when present | Parent experiment ID |
| `user_id` | TEXT | Required | Valid `user_id` | ID | Composite FK | Matches assignment when present | Converting user ID |
| `assignment_id` | TEXT | Optional | Valid `assignment_id` or `NULL` | ID | Composite FK `(assignment_id, experiment_id, user_id)` | Nullable; validated when non-null | Optional link to assignment |
| `conversion_type` | TEXT | Required | `Purchase`, `Refund`, `Payment_Failure`, `Complaint` | Enum | Non-unique | Checked enum | Outcome or guardrail event type |
| `conversion_timestamp` | TEXT | Required | ISO-8601 UTC | UTC Timestamp | Non-unique | Within conversion window for valid events | Event timestamp |
| `conversion_value` | REAL | Required | Real number | Currency (USD) | Non-unique | Default `0.0` | Monetary value of event |
| `conversion_status` | TEXT | Required | `Valid`, `Delayed_In_Window`, `Outside_Window`, `Incomplete_Telemetry` | Enum | Non-unique | Checked enum | Window & telemetry validity status |

## 7. `metric_definitions`
| Field Name | Data Type | Required | Allowed Values | Unit | Uniqueness | Validation Rule | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `metric_id` | TEXT | Required | `MET-EXP-...-V1` | ID | Primary Key | Append-only immutable | Versioned metric definition ID |
| `experiment_id` | TEXT | Required | Valid `experiment_id` | ID | FK | References `experiments` | Parent experiment ID |
| `metric_code` | TEXT | Required | `MET-EXP-...` | Code | `UNIQUE(experiment_id, metric_code, metric_version)` | Stable logical code across versions | Logical metric identifier |
| `metric_name` | TEXT | Required | Non-empty text | Text | Non-unique | Not null | Display name |
| `metric_type` | TEXT | Required | `Primary_Binary`, `Primary_Continuous`, `Guardrail_Rate` | Enum | Non-unique | Checked enum | Statistical family of metric |
| `metric_description` | TEXT | Required | Non-empty text | Text | Non-unique | Not null | Formula explanation |
| `numerator_definition` | TEXT | Required | Non-empty text | Rule | Non-unique | Not null | Exact numerator filter rule |
| `denominator_definition` | TEXT | Required | Non-empty text | Rule | Non-unique | Not null | Exact denominator population rule |
| `calculation_method` | TEXT | Required | `ITT_Proportion`, `Exposed_Proportion`, `ITT_Mean_Value` | Enum | Non-unique | Checked enum | Computation method |
| `metric_version` | INTEGER | Required | `1, 2, ...` | Version | `UNIQUE(experiment_id, metric_code, metric_version)` | Strictly sequential (`1, 2, ...`) | Monotonic version integer |
| `effective_from` | TEXT | Required | ISO-8601 UTC | UTC Timestamp | Non-unique | Strictly increasing with `metric_version` | Start of version validity window |
| `created_at` | TEXT | Required | ISO-8601 UTC | UTC Timestamp | Non-unique | Valid UTC string | Creation timestamp |

## 8. `guardrail_metrics`
| Field Name | Data Type | Required | Allowed Values | Unit | Uniqueness | Validation Rule | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `guardrail_id` | TEXT | Required | `GRD-EXP-2026-XXXXXX-XX` | ID | Primary Key | Non-empty unique ID | Unique guardrail ID |
| `experiment_id` | TEXT | Required | Valid `experiment_id` | ID | Composite FK | Matches metric's experiment | Parent experiment ID |
| `metric_id` | TEXT | Required | Valid `metric_id` | ID | Composite FK `(metric_id, experiment_id, metric_version)` | References `metric_definitions` | Guardrail metric definition ID |
| `metric_version` | INTEGER | Required | `>= 1` | Version | Composite FK | Matches `metric_definitions` | Bound metric version |
| `guardrail_name` | TEXT | Required | Non-empty text | Text | Non-unique | Not null | Human-readable guardrail name |
| `threshold_type` | TEXT | Required | `Absolute_Diff`, `Relative_Lift`, `Max_Rate` | Enum | Non-unique | Checked enum | Comparison scale |
| `threshold_value` | REAL | Required | Real number | Rate / Lift | Non-unique | Not null | Allowed threshold boundary |
| `comparison_direction` | TEXT | Required | `MAX_INCREASE`, `MIN_DECREASE`, `ABSOLUTE_CAP` | Enum | Non-unique | Checked enum | Direction of breach check |
| `severity` | TEXT | Required | `WARNING`, `CRITICAL` | Enum | Non-unique | Checked enum | Breach severity tier |
| `created_at` | TEXT | Required | ISO-8601 UTC | UTC Timestamp | Non-unique | Valid UTC string | Creation timestamp |

## 9. `experiment_results`
| Field Name | Data Type | Required | Allowed Values | Unit | Uniqueness | Validation Rule | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `result_id` | TEXT | Required | `RES-{run_id}-{var_id}-{code}-V{ver}-{method}` | ID | Primary Key | Append-only immutable | Deterministic result snapshot ID |
| `analysis_run_id` | TEXT | Required | `RUN-EXP-2026-XXXXXX-XXX` | ID | `UNIQUE(analysis_run_id, experiment_id, variant_id, metric_id, metric_version, analysis_method)` | Explicit run identifier | Analysis execution batch ID |
| `experiment_id` | TEXT | Required | Valid `experiment_id` | ID | Composite FK | References `experiments` | Parent experiment ID |
| `variant_id` | TEXT | Required | Valid `variant_id` | ID | Composite FK `(experiment_id, variant_id)` | Evaluated variant | Variant summarized by row |
| `control_variant_id` | TEXT | Required | Valid Control `variant_id` | ID | Composite FK `(experiment_id, control_variant_id, control_variant_type)` | Must be experiment's `Control` variant | Baseline Control variant ID |
| `control_variant_type` | TEXT | Required | `'Control'` | Constant | Composite FK | `CHECK (control_variant_type = 'Control')` | Enforces Control reference type |
| `metric_id` | TEXT | Required | Valid `metric_id` | ID | Composite FK `(metric_id, experiment_id, metric_version)` | References `metric_definitions` | Evaluated metric definition ID |
| `metric_version` | INTEGER | Required | `>= 1` | Version | Composite FK | Matches `metric_definitions` | Evaluated metric version |
| `analysis_method` | TEXT | Required | `ITT`, `EXPOSED_SECONDARY` | Enum | Part of unique grain | Checked enum | Population definition |
| `sample_size` | INTEGER | Required | `>= 0` | Users | Non-unique | Non-negative integer | Variant sample count |
| `numerator` | REAL | Required | Real number | Count / Sum | Non-unique | Matches source records | Metric numerator |
| `denominator` | REAL | Required | `>= 0.0` | Count | Non-unique | Non-negative float | Metric denominator |
| `metric_value` | REAL | Required | Real number | Rate / Mean | Non-unique | `numerator / denominator` | Calculated variant metric |
| `treatment_effect` | REAL | Optional | `NULL` (Control) / Float (Treatment) | Diff | Non-unique | `CI_low <= effect <= CI_high` for Treatment | Absolute difference vs Control |
| `relative_lift` | REAL | Optional | `NULL` (Control) / Float (Treatment) | Proportion | Non-unique | `(T - C) / C` when `C > 0` | Relative lift vs Control |
| `standard_error` | REAL | Optional | `NULL` (Control) / `>= 0.0` (Treatment) | SE | Non-unique | Non-negative for Treatment | Unpooled standard error of diff |
| `confidence_interval_lower` | REAL | Optional | `NULL` (Control) / Float (Treatment) | Diff | Non-unique | `<= treatment_effect` | 95% Newcombe-Wilson / Welch CI lower |
| `confidence_interval_upper` | REAL | Optional | `NULL` (Control) / Float (Treatment) | Diff | Non-unique | `>= treatment_effect` | 95% Newcombe-Wilson / Welch CI upper |
| `p_value` | REAL | Optional | `NULL` (Control) / `[0.0, 1.0]` (Treatment) | Probability | Non-unique | Pooled two-proportion z-test / Welch t-test | Two-sided hypothesis test p-value |
| `statistical_significance` | INTEGER | Optional | `NULL` (Control) / `0, 1` (Treatment) | Boolean int | Non-unique | `1` iff `p_value < significance_level` | Significance indicator |
| `guardrail_status` | TEXT | Required | `PASSED`, `WARNING`, `FAILED`, `INSUFFICIENT_DATA`, `NOT_APPLICABLE` | Enum | Non-unique | Checked enum | Aggregated guardrail outcome |
| `decision_status` | TEXT | Required | 9-state decision enum | Enum | Non-unique | `CONTROL_BASELINE` for Control; 8-priority table for Treatment | Launch recommendation status |
| `analysis_timestamp` | TEXT | Required | ISO-8601 UTC | UTC Timestamp | Non-unique | Point-in-time evaluation timestamp | Timestamp of analysis run |

## 10. `experiment_events` & 11. `experiment_issues`
- **`experiment_events`**: Stores `event_id` (PK), `experiment_id` (FK), `event_type`, `from_status` (nullable), `to_status`, `actor`, `notes`, and `event_timestamp`.
- **`experiment_issues`**: Stores `issue_id` (PK), `experiment_id` (FK), `affected_entity`, `affected_record_id`, `issue_type` (`DUPLICATE_ASSIGNMENT`, `EXPOSURE_BEFORE_ASSIGNMENT`, `OUTCOME_WINDOW_VIOLATION`, `SRM_DETECTED`, `METRIC_VERSION_MISMATCH`), `severity` (`WARNING`, `CRITICAL`), `detected_at`, `description`, `expected_behavior`, `actual_behavior`, and `resolution_status` (`Open`, `Acknowledged`, `Resolved`). Contains zero ground-truth fields.