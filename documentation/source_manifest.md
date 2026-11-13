# Synthetic Dataset Source Manifest

- **Generator Version**: `1.0.0`
- **Fixed Random Seed**: `20261022`
- **Reference Epoch Timestamp**: `2026-01-01T00:00:00Z`
- **PRNG Algorithm**: `numpy.random.PCG64` (`np.random.default_rng`)
- **Data Provenance**: 100% Synthetic Controlled Simulation (zero real customer or personal data)

## 1. Baseline Dataset Scales

The synthetic data generation engine supports two standard configuration presets:

| Mode | Experiments | Eligible Users / Exp | Total Eligible Users | Ineligible Users | Total Audience Rows | Configuration Object |
| :--- | :-: | ---: | ---: | ---: | ---: | :--- |
| **Starter Mode** | 5 | 500 | 2,500 | 250 | 2,750 | `config.settings.STARTER_CONFIG` |
| **Full Mode** | 10 | 5,000 | 50,000 | 5,000 | 55,000 | `config.settings.FULL_CONFIG` |

## 2. Actual Output Locations & Directories

Exported artifacts are partitioned into dedicated repository directories configured in `config/settings.py`:

| Output Target | Directory Path | Description |
| :--- | :--- | :--- |
| **Starter Mode Exports** | `data/starter/` | Canonical export directory for the 5-experiment Starter dataset (`STARTER_DATA_DIR`). Contains 24 deterministic export files when exported from Page 9 or via CLI. |
| **Full Mode Exports** | `data/full/` | Canonical export directory for the 10-experiment Full dataset (`FULL_DATA_DIR`). Contains 24 deterministic export files when exported from Page 9 or via CLI. |
| **Ground-Truth Benchmarks** | `data/ground_truth/` | External storage directory for isolated anomaly benchmark labels (`GROUND_TRUTH_DIR`). Contains `ground_truth.csv` and `ground_truth.json`. |

## 3. Generated File Types & Serialization Rules

Every export run (`exports/export_data.py`) enforces strict canonical formatting to guarantee identical SHA-256 cryptographic hashes across repeated executions:

1. **Canonical CSV Files (`*.csv`)**:
   - Encoded in `UTF-8` with standard Unix newline (`\n`) line endings.
   - Rows are ordered deterministically by primary key ascending (`ORDER BY {primary_key} ASC`).
   - Floating-point fields are formatted canonically using 8 decimal places (`{val:.8f}`).
   - Null values are emitted as empty strings (`""`).
2. **Canonical JSON Files (`*.json`)**:
   - Formatted with 2-space indentation and sorted dictionary keys (`indent=2, sort_keys=True`).
   - Floats are rounded to 8 decimal places to eliminate platform-dependent floating-point representation variations.
   - Encoded in `UTF-8` with trailing `\n`.
3. **Canonical SQL Seed Dump (`seed_data.sql`)**:
   - Fully self-contained transactional SQL script.
   - Begins with `PRAGMA foreign_keys = ON;` and `BEGIN TRANSACTION;`.
   - Contains explicit column-named `INSERT INTO {table} ({cols}) VALUES ({vals});` statements ordered by primary key.
   - Concludes with `COMMIT;`.
4. **Validation Summary & Checksum Manifest (`validation_summary.json`)**:
   - Contains execution metadata (`generator_version`, `random_seed`, `generation_timestamp`).
   - Contains full results of automated QA integrity checks (`validation_checks`).
   - Contains precision, recall, and detection coverage metrics against ground truth (`ground_truth_evaluation`).
   - Contains the live cryptographic manifest (`manifest`) array recording the exact SHA-256 hash, row count, and provenance for each exported file.
5. **Executive Evaluation Report (`experiment_evaluation_report.md`)**:
   - Standalone Markdown report summarizing portfolio launch decisions, confidence intervals, p-values, guardrail outcomes, and detected anomalies.

## 4. Complete Inventory of Exported Artifacts (24 Files per Mode)

Each export execution into `data/starter/` or `data/full/` generates exactly 24 files:

| # | Actual Filename | Format | Source Entity / Description |
| :-: | :--- | :-: | :--- |
| 1 | `experiments.csv` | CSV | Master experiment configurations and predeclared parameters |
| 2 | `experiments.json` | JSON | JSON serialization of `experiments` |
| 3 | `variants.csv` | CSV | Variant definitions, types (Control/Treatment), and traffic allocations |
| 4 | `variants.json` | JSON | JSON serialization of `variants` |
| 5 | `audience_members.csv` | CSV | Synthetic user profiles and eligibility statuses |
| 6 | `audience_members.json` | JSON | JSON serialization of `audience_members` |
| 7 | `assignments.csv` | CSV | Deterministic user variant allocations |
| 8 | `assignments.json` | JSON | JSON serialization of `assignments` |
| 9 | `exposure_events.csv` | CSV | Simulated user exposure telemetry |
| 10 | `exposure_events.json` | JSON | JSON serialization of `exposure_events` |
| 11 | `conversion_events.csv` | CSV | Simulated conversion and guardrail telemetry events |
| 12 | `conversion_events.json` | JSON | JSON serialization of `conversion_events` |
| 13 | `metric_definitions.csv` | CSV | Append-only versioned metric definitions |
| 14 | `metric_definitions.json` | JSON | JSON serialization of `metric_definitions` |
| 15 | `guardrail_metrics.csv` | CSV | Guardrail safety threshold configurations |
| 16 | `guardrail_metrics.json` | JSON | JSON serialization of `guardrail_metrics` |
| 17 | `experiment_results.csv` | CSV | Append-only statistical analysis snapshots |
| 18 | `experiment_results.json` | JSON | JSON serialization of `experiment_results` |
| 19 | `experiment_events.csv` | CSV | Experiment lifecycle state transition audit log |
| 20 | `experiment_events.json` | JSON | JSON serialization of `experiment_events` |
| 21 | `experiment_issues.csv` | CSV | Detected validation and anomaly records |
| 22 | `experiment_issues.json` | JSON | JSON serialization of `experiment_issues` |
| 23 | `ground_truth.csv` | CSV | Isolated benchmark labels copied from `data/ground_truth/` |
| 24 | `seed_data.sql` | SQL | Full transactional SQLite database seed script |

Additionally, two summary and audit artifacts are written to the target directory:
- `validation_summary.json` (cryptographic SHA-256 checksum manifest and QA audit)
- `experiment_evaluation_report.md` (portfolio statistical evaluation report)
