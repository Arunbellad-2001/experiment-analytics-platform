# Business Rules & Statistical Methodology

## 1. Experiment Lifecycle & Parameter Governance
1. **Strict Forward Lifecycle State Machine**:
   - Allowed transitions: `Draft -> Ready`, `Ready -> Running`, `Running -> Paused | Completed`, `Paused -> Running | Completed`, `Completed -> Archived`.
   - Returning to `Draft` from any non-Draft state or skipping states (e.g., `Draft -> Archived`, `Ready -> Archived`) is prohibited at both the SQLite trigger (`trg_experiments_lifecycle_transitions`) and service levels.
2. **Predeclared Parameter Locking**:
   - `primary_metric_code`, `minimum_detectable_effect` (MDE), and `significance_level` (alpha) can only be modified while an experiment remains in `Draft` status and before any `ExperimentResult` rows exist (`trg_experiments_lock_predeclared_parameters`).
   - `primary_metric_code` is the sole authoritative pointer to the primary metric and must reference a `Primary_Binary` or `Primary_Continuous` metric definition (`Guardrail_Rate` is rejected).
   - For `Primary_Binary` metrics, `0.0 <= minimum_detectable_effect <= 1.0` (absolute proportion difference scale). For `Primary_Continuous` metrics, `minimum_detectable_effect >= 0.0` in native metric units.

## 2. Randomization & Sample Ratio Mismatch (SRM)
1. **Eligible-Only Deterministic Assignment**:
   - Only `AudienceMember` rows with `eligibility_status = 'Eligible'` are assigned to variants.
   - Normal baseline generation enforces exactly one assignment per user per experiment (`ASG-EXP-...-USER-...`) using deterministic seeded PRNG streams (`seed = 20261022`).
2. **Chi-Square SRM Detection**:
   - Compares observed variant assignment counts against expected allocation percentages via `scipy.stats.chisquare`.
   - If `srm_p_value < 0.001`, `srm_detected = True` and a `CRITICAL` `SRM_DETECTED` issue is recorded in `experiment_issues`.

## 3. Intention-to-Treat (ITT) vs. Secondary Exposed Analysis
- **Primary Analysis (`ITT`)**: Evaluates all eligible assigned users according to their randomized variant assignment, regardless of downstream exposure noncompliance.
- **Secondary Analysis (`EXPOSED_SECONDARY`)**: Evaluates only users with a valid `Exposed` event occurring on or after `assigned_at`.

## 4. Statistical Inference Methodology
1. **Binary Conversion Metrics (`Primary_Binary`)**:
   - **Hypothesis Test (`p_value`)**: Two-sided pooled two-proportion z-test under `H0: p_T = p_C`.
   - **Confidence Interval**: 95% **Newcombe hybrid score interval** derived from single-proportion **Wilson score intervals** `(l_C, u_C)` and `(l_T, u_T)`.
   - **Statistical Significance**: `statistical_significance = 1` iff `p_value < experiments.significance_level` (enforced by SQLite trigger `trg_experiment_results_validate_significance`).
2. **Continuous Revenue/Value Metrics (`Primary_Continuous`)**:
   - Evaluated via two-sided **Welch's t-test** (`equal_var=False`) with Welch-Satterthwaite degrees of freedom for the 95% confidence interval.

## 5. Eight-Priority Launch Decision Precedence Table
1. **Priority 0 (`CONTROL_BASELINE`)**: Control reference row (`variant_id == control_variant_id`).
2. **Priority 1 (`INVALID_DATA_HOLD`)**: SRM detected or unresolved critical data integrity anomaly (`DUPLICATE_ASSIGNMENT`, `EXPOSURE_BEFORE_ASSIGNMENT`, `OUTCOME_WINDOW_VIOLATION`).
3. **Priority 2 (`RECALCULATION_REQUIRED`)**: Newer `metric_version` exists for `primary_metric_code` than the evaluated result's `metric_version`.
4. **Priority 3 (`DO_NOT_LAUNCH_GUARDRAIL_BREACH`)**: At least one guardrail has status `FAILED`.
5. **Priority 4 (`INSUFFICIENT_GUARDRAIL_DATA`)**: Zero guardrails `FAILED`, and at least one guardrail has status `INSUFFICIENT_DATA`.
6. **Priority 5 (`DO_NOT_LAUNCH_NO_SIGNIFICANT_LIFT`)**: `p_value >= significance_level` or `treatment_effect <= 0.0`.
7. **Priority 6 (`DO_NOT_LAUNCH_BELOW_MDE`)**: `p_value < significance_level` and `0.0 < treatment_effect < minimum_detectable_effect`.
8. **Priority 7 (`HOLD_FOR_GUARDRAIL_REVIEW`)**: Statistically and practically significant positive lift, zero `FAILED`/`INSUFFICIENT_DATA` guardrails, and at least one `WARNING` guardrail.
9. **Priority 8 (`LAUNCH_TREATMENT`)**: All gates passed (`PASSED` guardrails, `p_value < significance_level`, `treatment_effect >= minimum_detectable_effect`).