```markdown
# Changelog

All notable changes to the **Experiment Analytics Platform** are documented in this file.

## [1.0.0] - 2026-11-13 (Milestones 2–8: Complete End-to-End Platform Delivery)

### Features Added
- **Milestone 2**: Implemented `services/experiment_service.py`, `services/randomization.py`, `generator/master_data.py`, `generator/audience_generator.py`, `generator/assignment_generator.py`, and `tests/test_randomization.py`.
- **Milestone 3**: Implemented `generator/event_generator.py` and `tests/test_generator.py` simulating exposures, conversions, noncompliance, missing telemetry, and delayed conversions.
- **Milestone 4**: Implemented `services/metrics.py`, `services/statistics.py`, `services/guardrails.py`, `tests/test_metrics.py`, `tests/test_statistics.py`, and `tests/test_guardrails.py` with pooled two-proportion z-tests, Newcombe-Wilson 95% confidence intervals, Welch's t-tests, and the 8-priority launch decision engine.
- **Milestone 5**: Implemented `generator/anomaly_generator.py`, `generator/ground_truth.py`, `services/anomaly_detection.py`, `services/validation.py`, and `services/ground_truth_evaluator.py` covering all 5 negative edge cases with 100% Precision, Recall, and Coverage.
- **Milestone 6**: Implemented `generator/pipeline.py`, `exports/export_data.py`, `exports/report_generator.py`, and `tests/test_reproducibility.py` verifying identical SHA-256 checksums across repeated runs.
- **Milestone 7**: Implemented 9-page analytical Streamlit dashboard in `app.py`.
- **Milestone 8**: Completed `documentation/business_rules.md`, `documentation/validation_rules.md`, `documentation/testing_report.md`, `documentation/source_manifest.md`, `README.md`, and `ai_prompts/prompt_history.md`.

### Bug Fixes
- Clamped IEEE-754 boundary residuals in `wilson_score_interval` when `successes == 0` or `successes == total`.
- Assigned Edge Case 5 (`METRIC_VERSION_MISMATCH`) to `EXP-2026-000004` in 5-experiment Starter mode so Priority 1 (`INVALID_DATA_HOLD` on `EXP-2026-000005`) and Priority 2 (`RECALCULATION_REQUIRED` on `EXP-2026-000004`) are evaluated independently (`detection_coverage == 1.0`).

### Testing Performed
- Executed `python -m pytest -v`: **34 passed in 29.15s**.

## [0.1.0] - 2026-11-12 (Milestone 1: Project Scaffolding & Database Architecture)

### Features Added
- Initialized modular project structure, `config/settings.py`, `database/connection.py`, `database/schema.sql`, `database/models.py`, and `tests/test_database.py` (`9 passed`).