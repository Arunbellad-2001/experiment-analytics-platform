# AI Prompt History

This file maintains a chronological, auditable record of the prompts and architectural refinements submitted to AI tools during the design, development, testing, troubleshooting, and documentation of the **Experiment Analytics Platform**, in accordance with project transparency and confidentiality guidelines.

> **Disclosure Note**: All AI-assisted design, implementation, and debugging steps are documented transparently below. Confidential assessment instructions are summarized by technical scope rather than reproduced verbatim.

---

## Summary Table

| Entry | Date | AI Tool | Milestone / Stage | Purpose |
| :-: | :--- | :--- | :--- | :--- |
| 1 | 2026-11-11 | Gemini | Initial Blueprint | Establish modular architecture, 13-step synthetic generator design, 9 core entities, statistical/guardrail engines, 5 negative anomaly scenarios, 9-page Streamlit UI, and 8-milestone plan. |
| 2 | 2026-11-12 | Gemini | Architecture Refinement 1 | Confirm Starter (2,500 eligible / 5 exps) and Full (50,000 eligible / 10 exps) scales, isolate ground-truth labels to `data/ground_truth/`, resolve `Experiment` <-> `MetricDefinition` circularity, and enforce `PRAGMA foreign_keys = ON`. |
| 3 | 2026-11-12 | Gemini | Architecture Refinement 2 | Make `metric_definitions` and `experiment_results` 100% append-only, remove `ground_truth_reference` from `experiment_issues`, add composite FKs, specify pooled z-test + Newcombe-Wilson 95% CI, and designate `schema.sql` as canonical DDL. |
| 4 | 2026-11-12 | Gemini | Architecture Refinement 3 | Derive metric validity via `LEAD(effective_from)`, add `analysis_run_id` to `experiment_results`, enforce single `Control` variant via partial unique index and composite FK, add predeclared MDE, and separate `INSUFFICIENT_GUARDRAIL_DATA`. |
| 5 | 2026-11-12 | Gemini | Architecture Refinement 4 | Verify consistent `analysis_run_id` grain, `CHECK` constraints across all 7 comparative columns, and SQLite 3.25+ / Python 3.11–3.13 compatibility. |
| 6 | 2026-11-12 | Gemini | Architecture Refinement 5 | Lock MDE, `significance_level`, and `primary_metric_code` after `Draft` or once results exist; separate historical vs. live metric-version decisions; use `variant_id` in `result_id`; add `sqlite3` runtime version check (`>= 3.25.0`). |
| 7 | 2026-11-12 | Gemini | Architecture Refinement 6 | Prohibit returning to `Draft` via SQLite trigger, use `p_value < significance_level` + `treatment_effect > 0` as primary significance rule, and enforce metric-type-specific MDE bounds. |
| 8 | 2026-11-12 | Gemini | Architecture Refinement 7 & Final Approval | Enforce exact forward lifecycle state transitions, block atomic parameter edits during transition, reject `Guardrail_Rate` as primary metric, and enforce stored `statistical_significance` consistency via trigger. |
| 9 | 2026-11-12 | Gemini | Milestone 1: Implementation | Implement scaffolding, `.gitignore`, pinned `requirements.txt`, `config/settings.py`, `database/connection.py`, `database/schema.sql`, `database/models.py`, `tests/conftest.py`, and `tests/test_database.py`. |
| 10 | 2026-11-12 | Gemini | Milestone 1: Git Setup (CMD) | Create directory structure and placeholder files in Windows Command Prompt, initialize Git, and push initial `main` branch to GitHub. |
| 11 | 2026-11-12 | Gemini | Milestone 1: Environment & Verification | Set up `.venv`, install pinned packages, run `pytest` on `tests/test_database.py`, and commit/push Milestone 1 files. |
| 12 | 2026-11-12 | Gemini | Milestone 1: Step-by-Step File Delivery | Provide `config/` and `database/` files in sequential copy-paste blocks for Windows setup. |
| 13 | 2026-11-12 | Gemini | Milestone 1: Test Suite Delivery | Provide `tests/conftest.py` and `tests/test_database.py` with `pytest` verification instructions. |
| 14 | 2026-11-12 | Gemini | Milestone 1: Initial Docs Delivery | Provide `README.md`, `CHANGELOG.md`, `architecture.md`, `database_design.md`, and `data_dictionary.md`. |
| 15 | 2026-11-12 | Gemini | Milestone 1: Git Commit Fix | Move `CHANGELOG.md` from `logs/` to project root and push Milestone 1 commits to `origin/main`. |
| 16 | 2026-11-12 | Gemini | Project Roadmap Check | Summarize remaining milestones (Milestones 2–8) and pacing to completion. |
| 17 | 2026-11-12 | Gemini | Milestone 2: Implementation | Implement `services/experiment_service.py`, `services/randomization.py`, `generator/master_data.py`, `generator/audience_generator.py`, `generator/assignment_generator.py`, and `tests/test_randomization.py`. |
| 18 | 2026-11-13 | Gemini | Milestones 3–7: Full Implementation | Implement event simulation, metrics, statistics, guardrails, anomaly injection/detection, ground-truth evaluation, canonical exports, reproducibility tests, and the 9-page Streamlit dashboard (`app.py`). |
| 19 | 2026-11-13 | Gemini | Milestone 8 & Test/Runtime Fixes | Fix `wilson_score_interval` boundary clamping and Edge Case 5 experiment assignment (`34 passed`), use `python -m streamlit run app.py` for Windows Device Guard, and complete Milestone 8 docs. |
| 20 | 2026-11-13 | Gemini | Local SQLite & UI Guidance | Explain Python's built-in `sqlite3` local file database (`data/experiment_analytics.db`) and provide a 9-page dashboard walkthrough. |
| 21 | 2026-11-13 | Gemini | Windows `pyarrow` DLL Fix | Replace `st.dataframe` with a `pyarrow`-free HTML `render_table` helper in `app.py` to avoid Windows Application Control DLL blocks. |
| 22 | 2026-11-13 | Gemini | `app.py` Final Stability Fix | Fix `main()` call parentheses at the bottom of `app.py` and add a `sys.modules["pyarrow"]` fallback shim at startup. |
| 23 | 2026-11-13 | Gemini | Documentation Audit & Enhancement | Audit and update `README.md`, `architecture.md`, `database_design.md`, `testing_report.md`, `source_manifest.md`, and `business_rules.md` against the actual codebase without altering source code. |

---

## Detailed Prompt Log

### Entry 1 — Initial Project Blueprint (2026-11-11)
- **Tool**: Gemini
- **Purpose**: Establish the end-to-end architecture, technology stack, database design, synthetic data pipeline, statistical/guardrail engines, anomaly scenarios, Streamlit UI, and milestone workflow.
- **Prompt Summary (Confidential Assessment Details Redacted)**:
  > Design an end-to-end Experiment Analytics Platform in Python 3.11+ using Pandas, NumPy, SciPy, SQLite, SQLAlchemy ORM, Plotly, Streamlit, and pytest. Before writing code, summarize the modular architecture, major implementation risks, 9 core + supporting database entities, 8 development milestones, folder structure, deterministic reproducibility strategy (fixed seed `20261022`), cross-platform execution plan, and ambiguous assumptions requiring confirmation.

### Entry 2 — Architecture Refinement 1 (2026-11-12)
- **Tool**: Gemini
- **Purpose**: Confirm dataset scales, assignment uniqueness rules, ground-truth isolation, and schema corrections.
- **Prompt**:
  > Approve the Experiment Analytics Platform architecture with the following specifications: (1) Configure Starter mode for 2,500 eligible users across 5 experiments (500 per experiment) and Full mode for 50,000 eligible users across 10 experiments (5,000 per experiment) using identical generation logic and distinct synthetic users per experiment while preserving N:M schema flexibility; (2) Enforce single user-per-experiment assignment in baseline generation and validation services without a hard SQL UNIQUE constraint on `(experiment_id, user_id)` so deliberate duplicate-assignment anomalies can be stored and detected; (3) Store ground-truth labels exclusively in external CSV and JSON files under `data/ground_truth/` with zero database coupling or access from analytical services; (4) Resolve the circular dependency between `Experiment` and `MetricDefinition` using a versioned logical reference rather than a cyclic foreign key; (5) Enforce append-only immutability for `MetricDefinition` and `ExperimentResult`; (6) Pin all package dependencies for Python 3.11–3.13, enforce `PRAGMA foreign_keys = ON` on every SQLite connection, maintain strict ID naming patterns, and guarantee cross-platform deterministic SHA-256 exports. Provide the finalized database relationship design, ER diagram, folder structure, development milestones, technical assumptions, and risk mitigation table before starting Milestone 1.

### Entry 3 — Architecture Refinement 2 (2026-11-12)
- **Tool**: Gemini
- **Purpose**: Enforce strict append-only immutability, composite FKs, result grain, statistical methodology, and DDL source of truth.
- **Prompt**:
  > Finalize the Experiment Analytics Platform technical specifications prior to Milestone 1 by incorporating nine architectural corrections: (1) Enforce strict append-only immutability on `metric_definitions` (blocking all UPDATE and DELETE operations via SQLite triggers) and derive effective windows dynamically from `effective_from` across sequential versions; (2) Remove `ground_truth_reference` from `experiment_issues` so `ground_truth_evaluator.py` operates strictly read-only against operational tables and outputs separate evaluation artifacts; (3) Implement composite UNIQUE keys and composite FOREIGN KEY constraints across `variants`, `assignments`, `exposure_events`, and `conversion_events` to guarantee intra-experiment and intra-user referential consistency; (4) Explicitly define the `experiment_results` grain using a control-anchored variant metric row alongside a paired `compared_to_variant_id` reference so descriptive statistics and treatment comparisons never conflict; (5) Make `experiments.primary_metric_code` the single authoritative primary metric pointer and remove `is_primary` redundancy; (6) Specify the pooled two-proportion z-test for hypothesis testing (p-values) and the Newcombe method using Wilson score intervals for 95% confidence intervals of the difference in proportions; (7) Designate `database/schema.sql` as the canonical DDL source of truth verified against SQLAlchemy ORM metadata in automated tests; (8) Expand the test suite to verify composite FK enforcement, strict immutability, ground-truth isolation, and result-grain uniqueness; and (9) Specify the four-gate decision logic and output statuses. Provide only the revised sections, affected table definitions, updated ER diagram, and additional test cases.

### Entries 4 & 5 — Architecture Refinements 3 & 4 (2026-11-12)
- **Tool**: Gemini
- **Purpose**: Refine `LEAD(effective_from)` validity windows, `analysis_run_id`, single Control variant enforcement, `CHECK` constraints, MDE storage, and `INSUFFICIENT_GUARDRAIL_DATA`.
- **Prompt**:
  > Incorporate seven final architectural refinements prior to Milestone 1: (1) Remove `effective_to` and `superseded_by_version` from `metric_definitions`, enforce monotonically increasing `(metric_version, effective_from)` via a SQLite `BEFORE INSERT` trigger, and resolve the active metric version as of `analysis_timestamp` using `effective_from <= analysis_timestamp < LEAD(effective_from)`; (2) Remove `is_primary` from `metric_definitions` completely and validate that `experiments.primary_metric_code` resolves to an existing `metric_definitions` record for that experiment; (3) Add `analysis_run_id` to `experiment_results` as part of its primary grain, UNIQUE constraint, and `result_id` convention; (4) Enforce a single Control variant per experiment using a SQLite partial unique index `idx_variants_single_control ON variants(experiment_id) WHERE variant_type = 'Control'`, composite key validation, and service-level checks requiring exactly one Control variant; (5) Expand the `experiment_results` CHECK constraint to enforce NULL on all seven comparative fields for Control rows and validate non-null values, `0.0 <= p_value <= 1.0`, and `confidence_interval_lower <= treatment_effect <= confidence_interval_upper` for Treatment rows; (6) Store predeclared `minimum_detectable_effect` on `experiments` prior to analysis; and (7) Add `INSUFFICIENT_GUARDRAIL_DATA` as a distinct decision status separate from `DO_NOT_LAUNCH_GUARDRAIL_BREACH`. Return the corrected SQL definitions, updated ER diagram, updated decision-status table, additional test cases, and SQLite/Python 3.11–3.13 compatibility confirmation.

### Entry 6 — Architecture Refinement 5 (2026-11-12)
- **Tool**: Gemini
- **Purpose**: Lock MDE and significance level after Draft, separate historical vs. live metric-version decisions, stabilize `result_id`, and check SQLite runtime version.
- **Prompt**:
  > Incorporate five final adjustments prior to Milestone 1 without altering the approved architecture: (1) Define `minimum_detectable_effect` on the absolute treatment-effect scale (p_T - p_C for binary metrics; native unit difference for continuous metrics) alongside predeclared `significance_level` (alpha, default `0.05`) on `experiments`, and enforce via a SQLite `BEFORE UPDATE` trigger and service validation that neither field (nor `primary_metric_code`) can be modified once `OLD.experiment_status <> 'Draft'` or once rows exist in `experiment_results`; (2) Distinguish immutable historical `experiment_results` snapshots (which permanently record the calculation under the metric version active at `analysis_timestamp`) from live launch-decision evaluation (which flags `RECALCULATION_REQUIRED` if a newer metric version has been appended after `analysis_timestamp`); (3) Standardize `result_id` to `RES-{analysis_run_id}-{variant_id}-{metric_code}-V{metric_version}-{analysis_method}` using immutable `variant_id`; (4) Define the strict, exhaustive 8-level decision precedence table; and (5) Verify `sqlite3.sqlite_version_info >= (3, 25, 0)` during database initialization.

### Entry 7 — Architecture Refinement 6 (2026-11-12)
- **Tool**: Gemini
- **Purpose**: Enforce no-return-to-Draft lifecycle trigger, clarify p-value significance rule, and validate MDE scale by metric type.
- **Prompt**:
  > Apply three final specifications before starting Milestone 1: (1) Add a SQLite `BEFORE UPDATE` lifecycle trigger on `experiments` that prohibits transitioning back to `'Draft'` from any non-Draft status and enforces valid state transitions (`Draft -> Ready -> Running <-> Paused -> Completed -> Archived`), preserving the lock on `minimum_detectable_effect`, `significance_level`, and `primary_metric_code` across all non-Draft statuses; (2) Define statistical significance in Priority 5 of the decision precedence table strictly as `p_value < experiments.significance_level` with `treatment_effect > 0.0`, reporting the Newcombe-Wilson 95% confidence interval as supporting uncertainty estimation without using `confidence_interval_lower <= 0.0` as an independent rejection gate; and (3) Validate `minimum_detectable_effect` against the primary metric's `metric_type` (`0.0 <= MDE <= 1.0` for `Primary_Binary` and `MDE >= 0.0` for `Primary_Continuous`) in both SQLite triggers and service-layer validation.

### Entry 8 — Architecture Refinement 7 & Final Approval (2026-11-12)
- **Tool**: Gemini
- **Purpose**: Finalize exact lifecycle transitions, atomic parameter-lock trigger, primary metric type restriction, and stored significance trigger.
- **Prompt**:
  > Apply four final consistency corrections before Milestone 1: (1) Restrict `trg_experiments_lifecycle_transitions` and service validation to the exact state transitions (`Draft -> Ready`, `Ready -> Running`, `Running -> Paused | Completed`, `Paused -> Running | Completed`, `Completed -> Archived`, with no transitions out of `Archived` or back to `Draft`); (2) Update `trg_experiments_lock_predeclared_parameters` so `minimum_detectable_effect`, `significance_level`, and `primary_metric_code` cannot be modified when `OLD.experiment_status <> 'Draft'` OR `NEW.experiment_status <> 'Draft'` OR results exist in `experiment_results`; (3) Enforce in SQLite triggers and service validation that `experiments.primary_metric_code` must resolve to a `metric_definitions` row with `metric_type IN ('Primary_Binary', 'Primary_Continuous')` (explicitly rejecting `'Guardrail_Rate'`) before leaving `Draft`; and (4) Add a SQLite `BEFORE INSERT` trigger on `experiment_results` and service validation verifying that Treatment rows store `statistical_significance = 1` when `p_value < experiments.significance_level` and `0` when `p_value >= experiments.significance_level`.

### Entries 9–15 — Milestone 1 Implementation, Setup, Testing & Git Push (2026-11-12)
- **Tool**: Gemini
- **Purpose**: Implement Milestone 1 (`config/`, `database/`, `tests/test_database.py`, initial documentation), set up `.venv` and Git in Windows Command Prompt, verify `9 passed` in `pytest`, relocate `CHANGELOG.md` from `logs/`, and push to `origin/main`.
- **Prompt**:
  > Begin Milestone 1 following the 8-step workflow: create `.gitignore`, pinned `requirements.txt`, `config/settings.py`, `database/connection.py`, `database/schema.sql`, `database/models.py`, `tests/conftest.py`, `tests/test_database.py`, and initial documentation. Provide Windows Command Prompt setup instructions, sequential copy-paste file blocks, `pytest` verification steps, and Git commit/push commands.

### Entries 16–17 — Roadmap Check & Milestone 2 Implementation (2026-11-12)
- **Tool**: Gemini
- **Purpose**: Summarize remaining milestones (2–8) and implement Milestone 2 (`services/experiment_service.py`, `services/randomization.py`, `generator/master_data.py`, `generator/audience_generator.py`, `generator/assignment_generator.py`, `tests/test_randomization.py`).
- **Prompt**:
  > Summarize the remaining milestones and implement Milestone 2 (Synthetic Master Data, Audience Generation, Experiment Governance Service, and Randomization & SRM Engine) in one complete delivery with technical explanations, `pytest` execution commands, documentation updates, and Git commit commands.

### Entry 18 — Milestones 3–7 Consolidated Implementation (2026-11-13)
- **Tool**: Gemini
- **Purpose**: Deliver Milestones 3–7 (`event_generator.py`, `metrics.py`, `statistics.py`, `guardrails.py`, `anomaly_generator.py`, `ground_truth.py`, `anomaly_detection.py`, `validation.py`, `ground_truth_evaluator.py`, `pipeline.py`, `exports/`, `app.py`, and remaining `tests/`).
- **Prompt**:
  > Deliver the complete implementation for Milestones 3 through 7 of the Experiment Analytics Platform in a single consolidated response, including all remaining generators, analytical/statistical/guardrail/validation services, canonical exports, reproducibility tests, and the 9-page Streamlit dashboard (`app.py`).

### Entry 19 — Milestone 8 Documentation & Test/Runtime Fixes (2026-11-13)
- **Tool**: Gemini
- **Purpose**: Resolve 2 initial test failures (`wilson_score_interval` boundary clamping and Edge Case 5 experiment assignment) to achieve `34 passed`, provide `python -m streamlit run app.py` workaround for Windows Device Guard, and generate Milestone 8 documentation.
- **Prompt**:
  > Fix the boundary residual in `wilson_score_interval` and separate Edge Case 5 (`METRIC_VERSION_MISMATCH`) from `EXP-2026-000005` in Starter mode so all 34 tests pass (`detection_coverage == 1.0`). Provide the `python -m streamlit run app.py` command to bypass Windows Device Guard blocking `streamlit.exe`, along with the Milestone 8 documentation files.

### Entries 20–22 — Local SQLite Guidance & Windows `pyarrow` DLL Fixes (2026-11-13)
- **Tool**: Gemini
- **Purpose**: Explain Python's built-in `sqlite3` database engine and resolve Windows Application Control blocking `pyarrow.lib` inside Streamlit.
- **Prompt**:
  > Explain how SQLite runs locally via Python's built-in `sqlite3` without an external server and provide a 9-page UI guide. Then resolve `ImportError: DLL load failed while importing lib` on `pyarrow` by replacing `st.dataframe` with a `pyarrow`-free HTML `render_table` helper, fixing the missing `main()` parentheses, and adding a `sys.modules["pyarrow"]` startup stub in `app.py`.

### Entry 23 — Documentation Audit & Enhancement (2026-11-13)
- **Tool**: Gemini
- **Purpose**: Audit and update `README.md`, `architecture.md`, `database_design.md`, `testing_report.md`, `source_manifest.md`, and `business_rules.md` strictly against the verified implementation.
- **Prompt**:
  > Inspect the actual repository files and update `README.md`, `documentation/architecture.md`, `documentation/database_design.md`, `documentation/testing_report.md`, `documentation/source_manifest.md`, and `documentation/business_rules.md` with actual folder trees, Starter/Full export commands, Linux/macOS instructions, Mermaid architecture and 11-table ER diagrams, verified `pytest` environment/results (`34 passed`), exact export paths, and verified `NOT_APPLICABLE` guardrail behavior without modifying any source code or performing Git commits.