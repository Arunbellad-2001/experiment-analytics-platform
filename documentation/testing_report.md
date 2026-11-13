# Testing & Verification Report

## 1. Automated Test Suite Summary (`pytest`)
All **34 automated test cases** across 7 test modules execute against isolated temporary SQLite databases (`34 passed in 29.15s` on Python 3.13.7 / Windows 11):

| Test File | Test Cases | Coverage Focus | Expected Result | Actual Result |
| :--- | :-: | :--- | :---: | :---: |
| `tests/test_database.py` | 9 | SQLite `>= 3.25.0` check, ORM-to-DDL parity, composite FKs, single Control variant partial index, exact lifecycle state transitions, parameter locking, primary metric type & MDE bounds, append-only immutability triggers, Control/Treatment `CHECK` constraints, and significance trigger | `9 PASSED` | `9 PASSED` |
| `tests/test_randomization.py` | 5 | Starter master data & audience generation, eligible-only filtering, balanced (`50:50`) & unbalanced (`80:20`) allocations, Chi-square SRM detection, deterministic seed reproducibility, and service-level parameter guards | `5 PASSED` | `5 PASSED` |
| `tests/test_generator.py` | 1 | Exposure and conversion telemetry simulation, noncompliance, missing telemetry, delayed conversions, and baseline timestamp ordering | `1 PASSED` | `1 PASSED` |
| `tests/test_metrics.py` | 3 | Variant diagnostic reconciliation, point-in-time `LEAD(effective_from)` metric version lookup vs. live `RECALCULATION_REQUIRED` detection, and MDE scale validation | `3 PASSED` | `3 PASSED` |
| `tests/test_statistics.py` | 3 | Pooled two-proportion z-test, Newcombe-Wilson 95% confidence intervals (including boundary `x=0`), Welch's two-sample t-test, and p-value significance consistency | `3 PASSED` | `3 PASSED` |
| `tests/test_guardrails.py` | 11 | Guardrail breach detection (`FAILED`), `INSUFFICIENT_DATA` detection, and parametrized verification of all 9 decision statuses in the 8-priority precedence hierarchy | `11 PASSED` | `11 PASSED` |
| `tests/test_reproducibility.py` | 2 | Dual-run end-to-end 13-step pipeline reproducibility, identical SHA-256 export checksums across all 23+ artifacts, 100% anomaly precision/recall/coverage, and complete read-only ground-truth isolation (`total_changes() == 0`) | `2 PASSED` | `2 PASSED` |