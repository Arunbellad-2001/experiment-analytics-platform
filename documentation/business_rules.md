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

The platform evaluates experiment results through a deterministic priority cascade implemented in `services/statistics.py:resolve_decision_status`:

| Priority | Decision Status | Evaluation Conditions | Action Required |
| :-: | :--- | :--- | :--- |
| **0** | **`CONTROL_BASELINE`** | Evaluated row is the Control variant (`variant_id == control_variant_id`). | Reference baseline row; no launch action. |
| **1** | **`INVALID_DATA_HOLD`** | Critical data anomaly detected (`SRM_DETECTED`, `DUPLICATE_ASSIGNMENT`, `EXPOSURE_BEFORE_ASSIGNMENT`, `OUTCOME_WINDOW_VIOLATION`). | Halt experiment. Investigate instrumentation and telemetry pipelines. |
| **2** | **`RECALCULATION_REQUIRED`** | A newer `metric_version` exists in `metric_definitions` than the version recorded in this result row. | Re-run statistical analysis using the latest metric definition version. |
| **3** | **`DO_NOT_LAUNCH_GUARDRAIL_BREACH`** | At least one configured guardrail evaluates to `FAILED` (Critical severity threshold breached). | Do not launch. Treatment damages critical system or business metrics. |
| **4** | **`INSUFFICIENT_GUARDRAIL_DATA`** | Zero guardrails `FAILED`, but at least one guardrail has `INSUFFICIENT_DATA` (sample size below threshold of 30 users). | Continue experiment to collect sufficient sample size before making a launch decision. |
| **5** | **`DO_NOT_LAUNCH_NO_SIGNIFICANT_LIFT`** | `p_value >= significance_level` (statistically non-significant) or `treatment_effect <= 0.0` (negative/neutral effect). | Do not launch. Treatment fails to demonstrate statistically significant positive lift. |
| **6** | **`DO_NOT_LAUNCH_BELOW_MDE`** | `p_value < significance_level` and `0.0 < treatment_effect < minimum_detectable_effect`. | Do not launch. Statistically significant, but effect size is below predeclared practical threshold (MDE). |
| **7** | **`HOLD_FOR_GUARDRAIL_REVIEW`** | Statistically and practically significant positive lift, zero `FAILED`/`INSUFFICIENT_DATA` guardrails, but at least one `WARNING` guardrail. | Hold for stakeholder review. Lift is positive, but non-critical guardrails require sign-off. |
| **8** | **`LAUNCH_TREATMENT`** | All criteria satisfied: statistically significant positive lift exceeding MDE, with all guardrails evaluating to `PASSED`. | Launch treatment to 100% of production traffic. |

## 6. Guardrail Evaluation Engine & The `NOT_APPLICABLE` Status

The platform supports configurable guardrail metrics evaluated across three threshold types (`Absolute_Diff`, `Relative_Lift`, `Max_Rate`), two severity levels (`WARNING`, `CRITICAL`), and three comparison directions (`MAX_INCREASE`, `MIN_DECREASE`, `ABSOLUTE_CAP`).

The database schema (`database/schema.sql`) and ORM model (`database/models.py`) strictly enforce that `guardrail_status` must take one of five valid values:
```sql
CHECK (guardrail_status IN ('PASSED', 'WARNING', 'FAILED', 'INSUFFICIENT_DATA', 'NOT_APPLICABLE'))
```

### 1. The Five Guardrail Statuses Explained

- **`PASSED`**: All evaluated guardrails for the treatment variant stay within acceptable bounds (no thresholds breached).
- **`WARNING`**: At least one non-critical guardrail (`severity = 'WARNING'`) has breached its configured threshold, but no critical guardrails have breached.
- **`FAILED`**: At least one critical guardrail (`severity = 'CRITICAL'`) has breached its configured threshold (e.g. refund rate spike exceeding acceptable limits).
- **`INSUFFICIENT_DATA`**: The sample size / denominator for either the Control or Treatment variant is below `MIN_GUARDRAIL_DENOMINATOR` (30 users), meaning guardrail health cannot be determined with statistical confidence.
- **`NOT_APPLICABLE`**: Applied exclusively to the Control baseline variant.

### 2. When is a Guardrail Marked `NOT_APPLICABLE`?

`NOT_APPLICABLE` is assigned during analysis execution in `services/statistics.py:run_experiment_analysis` whenever the variant being evaluated is the verified Control variant:
```python
if v.variant_id == control_variant.variant_id:
    result_row = ExperimentResult(
        ...
        guardrail_status="NOT_APPLICABLE",
        decision_status="CONTROL_BASELINE",
        ...
    )
```

### 3. How `NOT_APPLICABLE` Differs from `PASSED` or `FAILED`

1. **Conceptual Purpose**:
   Guardrail evaluation is fundamentally a **comparative treatment-impact analysis**: it asks whether the *Treatment* experience introduces adverse regressions (such as higher checkout errors, higher cancellation rates, or reduced page speed) when compared against the established *Control* experience.
   Because the Control variant *is* the baseline reference itself, calculating a relative lift, delta, or regression of the Control against itself is mathematically undefined and conceptually meaningless.

2. **Integrity vs. False Equivalence**:
   - Labeling the Control variant as `PASSED` would be inaccurate because the Control was never subjected to an experimental intervention or safety threshold test.
   - Labeling the Control variant as `FAILED` would be erroneous and would trigger false-alarm guardrail alerts on the baseline system.
   - `NOT_APPLICABLE` correctly communicates that guardrail evaluation applies exclusively to Treatment interventions.

3. **Alignment with Schema Invariants**:
   Under the SQLite schema `CHECK` constraints on `experiment_results`, the Control row enforces `treatment_effect IS NULL`, `relative_lift IS NULL`, `standard_error IS NULL`, `p_value IS NULL`, and `statistical_significance IS NULL`. The `guardrail_status = 'NOT_APPLICABLE'` assignment aligns perfectly with this null-treatment invariant.

### 4. How `NOT_APPLICABLE` Affects the Experiment Launch Decision

- **Immediate Bypass of Launch Gates**:
  In `resolve_decision_status(...)`, Priority 0 intercepts the evaluation immediately:
  ```python
  if is_control:
      return "CONTROL_BASELINE"
  ```
- **Zero Risk of Blocking or Permitting Launches**:
  Because Priority 0 executes before any Treatment gates (Priorities 1 through 8), a `NOT_APPLICABLE` status never triggers `DO_NOT_LAUNCH_GUARDRAIL_BREACH`, `INSUFFICIENT_GUARDRAIL_DATA`, or `HOLD_FOR_GUARDRAIL_REVIEW`.
- **Reference Anchor Only**:
  The Control result row serves solely as the empirical baseline against which Treatment lift and guardrail deltas are measured. Only Treatment rows undergo launch decision evaluation.
