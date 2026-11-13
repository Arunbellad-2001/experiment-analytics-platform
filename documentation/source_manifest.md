# Synthetic Dataset Source Manifest

- **Generator Version**: `1.0.0`
- **Fixed Random Seed**: `20261022`
- **Reference Epoch Timestamp**: `2026-01-01T00:00:00Z`
- **PRNG Algorithm**: `numpy.random.PCG64` (`np.random.default_rng`)
- **Data Provenance**: 100% Synthetic Controlled Simulation (zero real customer or personal data)

## 1. Baseline Dataset Scales
| Mode | Experiments | Eligible Users / Exp | Total Eligible Users | Ineligible Users | Total Audience Rows |
| :--- | :-: | ---: | ---: | ---: | ---: |
| **Starter Mode (`STARTER_CONFIG`)** | 5 | 500 | 2,500 | 250 | 2,750 |
| **Full Mode (`FULL_CONFIG`)** | 10 | 5,000 | 50,000 | 5,000 | 55,000 |

## 2. Exported Files & Canonical Serialization Rules
Every export execution (`exports/export_data.py`) writes the following artifacts sorted deterministically by primary key ASC with UTF-8 encoding, `\n` line endings, and `.8f` floating-point precision, recording live SHA-256 checksums in `validation_summary.json`:
- `experiments.csv` / `experiments.json`
- `variants.csv` / `variants.json`
- `audience_members.csv` / `audience_members.json`
- `assignments.csv` / `assignments.json`
- `exposure_events.csv` / `exposure_events.json`
- `conversion_events.csv` / `conversion_events.json`
- `metric_definitions.csv` / `metric_definitions.json`
- `guardrail_metrics.csv` / `guardrail_metrics.json`
- `experiment_results.csv` / `experiment_results.json`
- `experiment_events.csv` / `experiment_events.json`
- `experiment_issues.csv` / `experiment_issues.json`
- `ground_truth.csv` / `ground_truth.json` (generated in `data/ground_truth/`)
- `seed_data.sql`
- `validation_summary.json` (contains live SHA-256 checksums for every exported file)
- `experiment_evaluation_report.md`