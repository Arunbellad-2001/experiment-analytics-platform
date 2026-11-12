# Experiment Analytics Platform

An end-to-end experimentation and A/B testing analytics platform built with Python 3.11+, SQLite, SQLAlchemy 2.0, Pandas, NumPy, SciPy, Plotly, and Streamlit.

## 1. Business Problem & Overview
Organizations running controlled experiments (such as testing a redesigned checkout experience against an existing control) must evaluate treatment lift while enforcing randomization integrity, metric versioning, guardrail safety, and data quality. This platform implements the complete experiment lifecycle:
1. Experiment design, hypothesis definition, and strict lifecycle state management (`Draft` -> `Ready` -> `Running` <-> `Paused` -> `Completed` -> `Archived`).
2. Reproducible synthetic audience and telemetry generation (Starter mode: 2,500 eligible users across 5 experiments; Full mode: 50,000 eligible users across 10 experiments; fixed seed `20261022`).
3. Deterministic variant assignment and Chi-square Sample Ratio Mismatch (SRM) validation.
4. Exposure and conversion event simulation supporting noncompliance, missing telemetry, and delayed conversions.
5. Versioned metric definitions, Intention-to-Treat (ITT) primary analysis, pooled two-proportion z-tests, Newcombe-Wilson 95% confidence intervals, and Welch's t-test for continuous metrics.
6. Guardrail monitoring and an 8-priority launch decision engine.
7. Blind detection of all 5 required negative anomaly scenarios and isolated ground-truth evaluation.

## 2. Technology Stack
- **Language**: Python 3.11 - 3.13
- **Database & ORM**: SQLite (`>= 3.25.0`) + SQLAlchemy 2.0
- **Analytics & Statistics**: NumPy, Pandas, SciPy
- **Frontend & Visualization**: Streamlit, Plotly
- **Testing**: pytest

## 3. Quickstart & Cross-Platform Setup

### Windows 10/11 (Command Prompt / PowerShell)
```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pytest -v