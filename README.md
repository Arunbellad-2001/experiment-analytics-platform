# Experiment Analytics Platform

An end-to-end experimentation and A/B testing analytics platform built with Python 3.11+, SQLite, SQLAlchemy 2.0, Pandas, NumPy, SciPy, Plotly, and Streamlit.

## 1. Business Problem & Overview
Organizations running controlled experiments (such as testing a redesigned checkout experience against an existing control) must evaluate treatment lift while enforcing randomization integrity, metric versioning, guardrail safety, and data quality. This platform implements the complete experiment lifecycle:
1. **Experiment Governance**: Hypothesis definition, predeclared Minimum Detectable Effect (MDE) and significance level (`alpha`), and strict forward lifecycle state management (`Draft -> Ready -> Running <-> Paused -> Completed -> Archived`).
2. **Reproducible Synthetic Data Engine**: Parameterized 13-step generator supporting **Starter mode** (2,500 eligible users across 5 experiments) and **Full mode** (50,000 eligible users across 10 experiments) with fixed seed `20261022`.
3. **Randomization & SRM Validation**: Deterministic user-to-variant assignment supporting balanced (`50:50`) and unbalanced (`80:20`, `70:30`) splits with Chi-square Sample Ratio Mismatch (`p < 0.001`) detection.
4. **Exposure & Conversion Simulation**: Models complete exposures, delayed telemetry, missing telemetry, noncompliant users, delayed conversions, and guardrail events (`Refund`, `Payment_Failure`, `Complaint`).
5. **Statistical & Guardrail Evaluation**: Intention-to-Treat (ITT) primary analysis and Exposed-Only secondary analysis, pooled two-proportion z-tests, Newcombe-Wilson 95% confidence intervals, Welch's two-sample t-test for continuous metrics, and an 8-priority launch decision engine.
6. **Blind Anomaly Detection & Isolated Ground-Truth Evaluation**: Detects all 5 required negative scenarios (`DUPLICATE_ASSIGNMENT`, `EXPOSURE_BEFORE_ASSIGNMENT`, `OUTCOME_WINDOW_VIOLATION`, `SRM_DETECTED`, `METRIC_VERSION_MISMATCH`) without reading ground-truth files and evaluates Precision, Recall, and Coverage against `data/ground_truth/`.
7. **9-Page Streamlit Dashboard & Canonical Exports**: Live SQLite-backed analytical pages plus deterministic CSV, JSON, SQL seed, and SHA-256 checksum manifest generation.

## 2. Technology Stack
- **Language**: Python 3.11 - 3.13 (tested on Python 3.13.7)
- **Database & ORM**: SQLite (`>= 3.25.0`, runtime `3.50.4`) + SQLAlchemy 2.0.36
- **Analytics & Statistics**: NumPy 2.1.3, Pandas 2.2.3, SciPy 1.14.1
- **Frontend & Visualization**: Streamlit 1.40.1, Plotly 5.24.1
- **Testing & Quality Assurance**: pytest 8.3.3 (`34 passed in 32.43s`)

## 3. Project Folder Structure

```text
experiment-analytics-platform/
├── app.py                          # 9-page Streamlit analytics dashboard
├── config/                         # Centralized configuration & runtime settings
│   ├── __init__.py
│   └── settings.py                 # Cross-platform paths, seeds, thresholds, vocabularies
├── database/                       # Relational storage & ORM layer
│   ├── __init__.py
│   ├── connection.py               # SQLite connection, session scope, PRAGMA setup
│   ├── models.py                   # SQLAlchemy 2.0 ORM mappings for 11 entities
│   └── schema.sql                  # Authoritative SQLite DDL, triggers, and partial indexes
├── generator/                      # 13-step synthetic data generation pipeline
│   ├── __init__.py
│   ├── anomaly_generator.py        # Injects 5 controlled negative edge-case anomalies
│   ├── assignment_generator.py     # Deterministic PRNG randomization & variant assignment
│   ├── audience_generator.py       # User profiles & eligibility status generator
│   ├── event_generator.py          # Exposure & conversion event telemetry simulation
│   ├── ground_truth.py             # Writes isolated ground-truth benchmark files
│   ├── master_data.py              # Experiments, variants, metrics, and guardrail rules
│   └── pipeline.py                 # 13-step generation orchestrator & reset utilities
├── services/                       # Business logic, statistics, and validation services
│   ├── __init__.py
│   ├── anomaly_detection.py        # Blind anomaly detection engine
│   ├── experiment_service.py       # Lifecycle governance & experiment querying
│   ├── ground_truth_evaluator.py   # Read-only evaluation of precision, recall, coverage
│   ├── guardrails.py               # Multi-threshold guardrail safety evaluation engine
│   ├── metrics.py                  # ITT vs. Exposed-only metric aggregation & versioning
│   ├── randomization.py            # Variant assignment algorithms & SRM checks
│   ├── statistics.py               # Pooled z-tests, Welch t-tests, Newcombe CIs, decision engine
│   └── validation.py               # Integrity checks across all 11 database entities
├── exports/                        # Canonical export and reporting utilities
│   ├── __init__.py
│   ├── export_data.py              # Canonical CSV, JSON, SQL seed, and SHA-256 export
│   └── report_generator.py         # Executive Markdown evaluation report generator
├── data/                           # Relational database and exported dataset files
│   ├── experiment_analytics.db     # SQLite operational database (11 tables)
│   ├── starter/                    # Starter Mode canonical exports (2,500 users / 5 exps)
│   ├── full/                       # Full Mode canonical exports (50,000 users / 10 exps)
│   └── ground_truth/               # Benchmark ground-truth files (CSV & JSON)
├── documentation/                  # Comprehensive technical documentation
│   ├── architecture.md             # System architecture, components, and data flow
│   ├── business_rules.md           # Lifecycle governance, decision rules, NOT_APPLICABLE status
│   ├── database_design.md          # 11-table ERD, foreign keys, triggers, and indexes
│   ├── data_dictionary.md          # Complete schema definitions, column types, and constraints
│   ├── source_manifest.md          # Export file locations, formats, and SHA-256 rules
│   ├── testing_report.md           # Automated test results, execution commands, environment
│   └── validation_rules.md         # Data integrity, SRM, and anomaly detection rules
├── tests/                          # Automated test suite (34 pytest cases)
│   ├── __init__.py
│   ├── conftest.py                 # Database fixtures and session setup
│   ├── test_database.py            # DDL, triggers, foreign keys, constraints
│   ├── test_generator.py           # Exposure/conversion telemetry simulation
│   ├── test_guardrails.py          # Guardrail breaches & 8-priority decision table
│   ├── test_metrics.py             # Metric calculations, versioning, MDE scale
│   ├── test_randomization.py       # Randomization, seed reproducibility, SRM checks
│   ├── test_reproducibility.py     # Dual-run pipeline reproducibility & SHA-256 match
│   └── test_statistics.py          # Statistical tests, p-values, confidence intervals
├── logs/                           # Application runtime logs
│   ├── .gitkeep
│   └── platform.log                # Platform execution log file
├── ai_prompts/                     # Recorded prompt history
│   └── prompt_history.md
├── requirements.txt                # Pinned dependencies
├── CHANGELOG.md                    # Release history
└── README.md                       # Project documentation entry point
```

## 4. Cross-Platform Installation & Execution

### Windows 10/11 (Command Prompt / PowerShell)
```cmd
:: Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

:: Upgrade pip and install pinned dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

:: Run the complete automated test suite
python -m pytest -v

:: Launch the Streamlit analytical dashboard
python -m streamlit run app.py
```

### Linux & macOS (bash / zsh)
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip and install pinned dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Run the complete automated test suite
python -m pytest -v

# Launch the Streamlit analytical dashboard
python -m streamlit run app.py
```

After launching Streamlit, open your browser at `http://localhost:8501`.

## 5. Dataset Generation & Canonical Exports

The platform supports two dataset scales:
- **Starter Mode (`STARTER_CONFIG`)**: 5 experiments, 500 eligible users per experiment (2,500 total eligible users), 250 ineligible users (2,750 total audience rows), fixed seed `20261022`.
- **Full Mode (`FULL_CONFIG`)**: 10 experiments, 5,000 eligible users per experiment (50,000 total eligible users), 5,000 ineligible users (55,000 total audience rows), fixed seed `20261022`.

Datasets and canonical exports can be generated either interactively via the Streamlit web dashboard or programmatically via the command line.

### Option A: Interactive Generation via Streamlit Web UI
1. Start the Streamlit application (`streamlit run app.py`).
2. Navigate to **Page 3: Synthetic Data Generation Engine** in the sidebar.
3. Select your desired preset: **"Starter (2,500 users / 5 exps)"** or **"Full (50,000 users / 10 exps)"**.
4. Keep the random seed set to `20261022` and toggle **"Inject 5 Labelled Anomaly Edge Cases"** enabled.
5. Click **"Run 13-Step Synthetic Data Pipeline"**.
6. To export canonical files, navigate to **Page 9: Canonical Exports & Audit Manifest**, choose the target folder (`data/starter` or `data/full`), and click **"Generate All Canonical Exports (CSV, JSON, SQL, SHA-256 Manifest)"**.

### Option B: Command-Line Generation & Export (CLI)

#### 1. Generate Starter Mode Dataset
```bash
python -c "from database.connection import init_db; from config.settings import DEFAULT_DB_PATH, STARTER_CONFIG; from generator.pipeline import run_generation_pipeline; engine = init_db(DEFAULT_DB_PATH); summary = run_generation_pipeline(engine, config=STARTER_CONFIG, inject_anomalies=True); print(f'Successfully generated {summary.mode_name} mode: {summary.entity_counts}')"
```

#### 2. Generate Full Mode Dataset
```bash
python -c "from database.connection import init_db; from config.settings import DEFAULT_DB_PATH, FULL_CONFIG; from generator.pipeline import run_generation_pipeline; engine = init_db(DEFAULT_DB_PATH); summary = run_generation_pipeline(engine, config=FULL_CONFIG, inject_anomalies=True); print(f'Successfully generated {summary.mode_name} mode: {summary.entity_counts}')"
```

#### 3. Export Canonical Artifacts to `data/starter/`
```bash
python -c "from database.connection import init_db, session_scope; from config.settings import DEFAULT_DB_PATH, STARTER_DATA_DIR, GROUND_TRUTH_DIR; from exports.export_data import export_all_datasets; from exports.report_generator import generate_experiment_markdown_report; engine = init_db(DEFAULT_DB_PATH); session = session_scope(engine).__enter__(); export_all_datasets(session, output_dir=STARTER_DATA_DIR, ground_truth_dir=GROUND_TRUTH_DIR); (STARTER_DATA_DIR / 'experiment_evaluation_report.md').write_text(generate_experiment_markdown_report(session), encoding='utf-8'); print('Starter export completed successfully to data/starter/')"
```

#### 4. Export Canonical Artifacts to `data/full/`
```bash
python -c "from database.connection import init_db, session_scope; from config.settings import DEFAULT_DB_PATH, FULL_DATA_DIR, GROUND_TRUTH_DIR; from exports.export_data import export_all_datasets; from exports.report_generator import generate_experiment_markdown_report; engine = init_db(DEFAULT_DB_PATH); session = session_scope(engine).__enter__(); export_all_datasets(session, output_dir=FULL_DATA_DIR, ground_truth_dir=GROUND_TRUTH_DIR); (FULL_DATA_DIR / 'experiment_evaluation_report.md').write_text(generate_experiment_markdown_report(session), encoding='utf-8'); print('Full export completed successfully to data/full/')"
```

Each export run produces 24 artifacts: 11 CSV files, 11 JSON files, `seed_data.sql`, `validation_summary.json` (containing cryptographic SHA-256 checksums), and `experiment_evaluation_report.md`.

## 6. Application Dashboard & UI Pages (Screenshots)

The platform provides a 9-page analytical Streamlit dashboard accessible from the navigation sidebar. Below are descriptions and placeholder references for all nine application views:

### Page 1: Platform Overview & Portfolio Dashboard
High-level executive overview featuring key portfolio metrics (total experiments, active experiments, overall launch decisions, and system health status) alongside an interactive portfolio table and decision distribution charts.

![Page 1: Platform Overview & Portfolio Dashboard](docs/screenshots/page_1_overview.png)
> *Screenshot placeholder: Capture from `http://localhost:8501` (Page 1: Platform Overview & Portfolio Dashboard)*

---

### Page 2: Experiment Lifecycle & Configuration
Interactive experiment governance console supporting the strict forward state machine (`Draft -> Ready -> Running <-> Paused -> Completed -> Archived`), parameter locking, metric definition inspectability, and lifecycle event audit logs.

![Page 2: Experiment Lifecycle & Configuration](docs/screenshots/page_2_lifecycle.png)
> *Screenshot placeholder: Capture from `http://localhost:8501` (Page 2: Experiment Lifecycle & Configuration)*

---

### Page 3: Synthetic Data Generation Engine
Console for running the parameterized 13-step synthetic data generation pipeline. Allows selecting Starter, Full, or Custom scale presets, configuring random seeds, toggling labelled anomaly injection, and viewing entity generation summaries.

![Page 3: Synthetic Data Generation Engine](docs/screenshots/page_3_data_generation.png)
> *Screenshot placeholder: Capture from `http://localhost:8501` (Page 3: Synthetic Data Generation Engine)*

---

### Page 4: Randomization & Sample Ratio Mismatch (SRM) Validation
Validates user variant assignments against configured traffic allocation ratios (e.g. `50:50`, `80:20`, `70:30`). Displays observed vs. expected assignment counts, Chi-square test statistics, p-values, and SRM alerts.

![Page 4: Randomization & SRM Validation](docs/screenshots/page_4_randomization_srm.png)
> *Screenshot placeholder: Capture from `http://localhost:8501` (Page 4: Randomization & Sample Ratio Mismatch Validation)*

---

### Page 5: Exposure & Conversion Event Analytics
Visualizes telemetry funnels, exposure latency distributions, noncompliant user rates, conversion timelines, and conversion window compliance across experiments and variants.

![Page 5: Exposure & Conversion Event Analytics](docs/screenshots/page_5_event_analytics.png)
> *Screenshot placeholder: Capture from `http://localhost:8501` (Page 5: Exposure & Conversion Event Analytics)*

---

### Page 6: Statistical Analysis & Hypothesis Testing
Detailed statistical inference view presenting Intention-to-Treat (ITT) vs. Exposed-Only secondary analyses, two-proportion z-tests, Welch's t-tests, Newcombe-Wilson 95% confidence intervals, and the 8-priority launch decision status.

![Page 6: Statistical Analysis & Hypothesis Testing](docs/screenshots/page_6_statistical_analysis.png)
> *Screenshot placeholder: Capture from `http://localhost:8501` (Page 6: Statistical Analysis & Hypothesis Testing)*

---

### Page 7: Guardrail Metric Monitoring
Monitors secondary safety metrics (Refund Rate, Payment Failure Rate, Customer Complaint Rate) against predefined thresholds. Displays comparison directions (`MAX_INCREASE`, `MIN_DECREASE`, `ABSOLUTE_CAP`), severity flags (`WARNING`, `CRITICAL`), and evaluation outcomes (`PASSED`, `WARNING`, `FAILED`, `INSUFFICIENT_DATA`, `NOT_APPLICABLE`).

![Page 7: Guardrail Metric Monitoring](docs/screenshots/page_7_guardrails.png)
> *Screenshot placeholder: Capture from `http://localhost:8501` (Page 7: Guardrail Metric Monitoring)*

---

### Page 8: Anomaly Detection & Ground-Truth Verification
Blind anomaly detection audit center displaying detected issues across all 5 negative edge cases (`DUPLICATE_ASSIGNMENT`, `EXPOSURE_BEFORE_ASSIGNMENT`, `OUTCOME_WINDOW_VIOLATION`, `SRM_DETECTED`, `METRIC_VERSION_MISMATCH`). Compares detections against external ground truth to demonstrate 100% Precision, 100% Recall, and 100% Coverage.

![Page 8: Anomaly Detection & Ground-Truth Verification](docs/screenshots/page_8_anomaly_detection.png)
> *Screenshot placeholder: Capture from `http://localhost:8501` (Page 8: Anomaly Detection & Ground-Truth Verification)*

---

### Page 9: Canonical Exports & Audit Manifest
Export and verification hub providing one-click generation and downloads of canonical CSVs, JSONs, `seed_data.sql`, `validation_summary.json` (with SHA-256 checksums), and executive Markdown evaluation reports.

![Page 9: Canonical Exports & Audit Manifest](docs/screenshots/page_9_exports_manifest.png)
> *Screenshot placeholder: Capture from `http://localhost:8501` (Page 9: Canonical Exports & Audit Manifest)*
