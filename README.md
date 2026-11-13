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
- **Language**: Python 3.11 - 3.13
- **Database & ORM**: SQLite (`>= 3.25.0`) + SQLAlchemy 2.0
- **Analytics & Statistics**: NumPy, Pandas, SciPy
- **Frontend & Visualization**: Streamlit, Plotly
- **Testing**: pytest (`34 passed`)

## 3. Cross-Platform Installation & Execution

### Windows 10/11 (Command Prompt / PowerShell)
```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest -v
python -m streamlit run app.py