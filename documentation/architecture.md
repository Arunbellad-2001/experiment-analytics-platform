# Architecture Overview

## 1. Layered Design
The Experiment Analytics Platform separates persistence, synthetic data generation, statistical/validation business logic, data exports, and presentation into independent packages:
- **`config/`**: Cross-platform `pathlib.Path` constants, deterministic seed (`20261022`), Starter (2,500 eligible users / 5 experiments) and Full (50,000 eligible users / 10 experiments) configurations, and controlled vocabularies.
- **`database/`**: Authoritative SQLite schema (`schema.sql`), SQLAlchemy 2.0 ORM models (`models.py`), runtime SQLite version check (`>= 3.25.0`), and `PRAGMA foreign_keys = ON` connection management (`connection.py`).
- **`generator/`**: Parameterized 13-step synthetic data generation pipeline using isolated `numpy.random.default_rng` streams.
- **`services/`**: Experiment lifecycle governance, randomization and SRM validation, versioned metric calculation, statistical inference (pooled two-proportion z-test and Newcombe-Wilson 95% confidence intervals), guardrail evaluation, blind anomaly detection, and read-only ground-truth evaluation.
- **`exports/`**: Canonical CSV, JSON, SQL seed, and SHA-256 manifest generators.
- **`app.py`**: 9-page analytical Streamlit interface backed by live SQLite queries.

## 2. Ground-Truth Isolation Principle
Operational analysis and anomaly detection services query only the 11 operational SQLite tables. Ground-truth labels are stored exclusively in external files under `data/ground_truth/` (`ground_truth.csv` and `ground_truth.json`) and are read only by `services/ground_truth_evaluator.py` after anomaly detection has completed.