# Testing & Verification Report

## 1. Environment & Runtime Specifications

The automated test suite was executed in an isolated Python virtual environment against dynamic temporary SQLite databases:

- **Operating System**: Microsoft Windows 11 Enterprise / Pro (64-bit, NT 10.0.26300, `platform win32`)
- **Python Version**: `3.13.7`
- **Database Engine**: SQLite `3.50.4` (exceeds minimum platform requirement of `>= 3.25.0`)
- **Test Runner**: `pytest 8.3.3` (with `pluggy 1.7.0`)
- **Core Pinned Dependencies**:
  - `SQLAlchemy==2.0.36`
  - `numpy==2.1.3`
  - `pandas==2.2.3`
  - `scipy==1.14.1`
  - `streamlit==1.40.1`
  - `plotly==5.24.1`

## 2. Test Execution Command

The test suite was executed using the following command from the project root:

```powershell
# Windows PowerShell / Command Prompt (with active virtual environment)
.venv\Scripts\python.exe -m pytest -v

# Cross-platform alternative
python -m pytest -v
```

## 3. Test Execution Summary

```text
============================= test session starts =============================
platform win32 -- Python 3.13.7, pytest-8.3.3, pluggy-1.7.0 -- D:\experiment-analytics-platform\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\experiment-analytics-platform
collected 34 items

tests/test_database.py::test_sqlite_runtime_version_check PASSED         [  2%]
tests/test_database.py::test_schema_sql_and_orm_metadata_parity PASSED   [  5%]
tests/test_database.py::test_composite_referential_integrity PASSED      [  8%]
tests/test_database.py::test_single_control_variant_and_result_control_fk PASSED [ 11%]
tests/test_database.py::test_exact_lifecycle_state_machine PASSED        [ 14%]
tests/test_database.py::test_atomic_transition_and_parameter_modification_blocked PASSED [ 17%]
tests/test_database.py::test_primary_metric_rejects_guardrail_rate_and_enforces_mde_scale PASSED [ 20%]
tests/test_database.py::test_metric_version_append_only_and_lead_window_lookup PASSED [ 23%]
tests/test_database.py::test_experiment_results_check_constraints_immutability_and_significance_trigger PASSED [ 26%]
tests/test_generator.py::test_exposure_and_conversion_simulation_integrity PASSED [ 29%]
tests/test_guardrails.py::test_guardrail_breach_detection_on_experiment_3 PASSED [ 32%]
tests/test_guardrails.py::test_insufficient_guardrail_data_status PASSED [ 35%]
tests/test_guardrails.py::test_strict_decision_precedence_hierarchy[True-False-False-NOT_APPLICABLE-None-None-0.02-CONTROL_BASELINE] PASSED [ 38%]
tests/test_guardrails.py::test_strict_decision_precedence_hierarchy[False-True-False-PASSED-0.001-0.05-0.02-INVALID_DATA_HOLD] PASSED [ 41%]
tests/test_guardrails.py::test_strict_decision_precedence_hierarchy[False-False-True-PASSED-0.001-0.05-0.02-RECALCULATION_REQUIRED] PASSED [ 44%]
tests/test_guardrails.py::test_strict_decision_precedence_hierarchy[False-False-False-FAILED-0.001-0.05-0.02-DO_NOT_LAUNCH_GUARDRAIL_BREACH] PASSED [ 47%]
tests/test_guardrails.py::test_strict_decision_precedence_hierarchy[False-False-False-INSUFFICIENT_DATA-0.001-0.05-0.02-INSUFFICIENT_GUARDRAIL_DATA] PASSED [ 50%]
tests/test_guardrails.py::test_strict_decision_precedence_hierarchy[False-False-False-PASSED-0.12-0.05-0.02-DO_NOT_LAUNCH_NO_SIGNIFICANT_LIFT] PASSED [ 52%]
tests/test_guardrails.py::test_strict_decision_precedence_hierarchy[False-False-False-PASSED-0.005-0.012-0.02-DO_NOT_LAUNCH_BELOW_MDE] PASSED [ 55%]
tests/test_guardrails.py::test_strict_decision_precedence_hierarchy[False-False-False-WARNING-0.005-0.035-0.02-HOLD_FOR_GUARDRAIL_REVIEW] PASSED [ 58%]
tests/test_guardrails.py::test_strict_decision_precedence_hierarchy[False-False-False-PASSED-0.005-0.035-0.02-LAUNCH_TREATMENT] PASSED [ 61%]
tests/test_metrics.py::test_variant_diagnostics_and_itt_vs_exposed_metrics PASSED [ 64%]
tests/test_metrics.py::test_historical_vs_current_metric_version_decision PASSED [ 67%]
tests/test_metrics.py::test_mde_validation_by_metric_type PASSED         [ 70%]
tests/test_randomization.py::test_starter_master_data_and_audience_generation PASSED [ 73%]
tests/test_randomization.py::test_eligible_only_assignment_and_no_duplicates PASSED [ 76%]
tests/test_randomization.py::test_balanced_and_unbalanced_randomization_and_srm_validation PASSED [ 79%]
tests/test_randomization.py::test_deterministic_assignment_reproducibility PASSED [ 82%]
tests/test_randomization.py::test_service_level_validation_and_parameter_locking PASSED [ 85%]
tests/test_reproducibility.py::test_end_to_end_reproducibility_and_sha256_checksums PASSED [ 88%]
tests/test_reproducibility.py::test_ground_truth_complete_isolation PASSED [ 91%]
tests/test_statistics.py::test_pooled_z_test_and_newcombe_wilson_ci PASSED [ 94%]
tests/test_statistics.py::test_continuous_welch_t_test PASSED            [ 97%]
tests/test_statistics.py::test_p_value_statistical_significance_consistency PASSED [100%]

============================= 34 passed in 32.43s =============================
```

- **Total Tests Collected**: 34
- **Passed**: 34 (100%)
- **Failed**: 0
- **Skipped**: 0
- **Execution Time**: 32.43 seconds

## 4. Module-Level Verification Details

| Test File | Test Cases | Verification Scope & Tested Invariants | Actual Result |
| :--- | :-: | :--- | :---: |
| `tests/test_database.py` | 9 | Verifies SQLite `>= 3.25.0` check, complete parity between DDL (`schema.sql`) and SQLAlchemy ORM metadata (`models.py`), composite referential integrity, partial index enforcing at most 1 Control variant per experiment (`idx_variants_single_control`), strict forward lifecycle transitions (`Draft -> Ready -> Running <-> Paused -> Completed -> Archived`), parameter locking on non-draft experiments, primary metric restrictions against guardrail rate definitions, append-only immutability triggers on metric definitions and results, and significance trigger synchronization. | `9 PASSED` |
| `tests/test_generator.py` | 1 | Evaluates end-to-end telemetry generation, verifying chronological order (`assigned_at <= exposure_timestamp`), simulated telemetry delays, noncompliant users, conversion window filtering, and realistic drop-offs. | `1 PASSED` |
| `tests/test_guardrails.py` | 11 | Tests guardrail breach detection on Experiment 3 (Aggressive Countdown Timer), `INSUFFICIENT_DATA` detection when sample size is below threshold (< 30 users), and parametrized validation of all 9 outcomes across the strict 8-priority launch decision table (including `NOT_APPLICABLE` for Control baseline). | `11 PASSED` |
| `tests/test_metrics.py` | 3 | Verifies ITT vs. Exposed-Only calculation algorithms, point-in-time version resolution via `LEAD(effective_from)`, `RECALCULATION_REQUIRED` detection when newer metric versions exist, and MDE scale validations (bounded proportion for binary vs. unbounded positive for continuous). | `3 PASSED` |
| `tests/test_randomization.py` | 5 | Validates audience member generation, eligible-only variant assignment, zero duplicates in baseline assignment generation, deterministic PRNG seed reproducibility (`seed=20261022`), balanced (`50:50`) and unbalanced (`80:20`) allocations, Chi-square Sample Ratio Mismatch (`srm_p_value < 0.001`) detection, and service-level parameter validation guards. | `5 PASSED` |
| `tests/test_reproducibility.py` | 2 | Executes dual independent pipeline runs with identical seed `20261022` to prove 100% identical SHA-256 checksums across all 24 export artifacts, perfect anomaly detection metrics (Precision: 1.0, Recall: 1.0, Coverage: 1.0), and physical ground-truth isolation (`SELECT total_changes() == 0`). | `2 PASSED` |
| `tests/test_statistics.py` | 3 | Tests two-proportion pooled z-tests, Newcombe-Wilson hybrid score confidence intervals (including edge cases such as zero conversions), Welch's two-sample t-test for continuous metrics, and strict p-value significance alignment (`p_value < alpha`). | `3 PASSED` |
