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

## 3. End-to-End System Architecture Diagram

The diagram below illustrates the end-to-end data flow through all primary components of the Experiment Analytics Platform:

```mermaid
flowchart TD
    subgraph ConfigLayer["1. Configuration & Deterministic Seed Control"]
        CFG["config/settings.py<br/>Fixed Seed (20261022)<br/>Starter & Full Scale Configs"]
    end

    subgraph DataGen["2. Synthetic Data Generation Engine (generator/)"]
        GEN["generator/pipeline.py (13 Steps)"]
        MD["Master Data<br/>(Experiments, Variants,<br/>Metrics, Guardrails)"]
        AUD["Audience & Eligibility<br/>(AudienceMember)"]
        ASG["Randomization & Assignment<br/>(Assignments)"]
        EVT["Telemetry Simulation<br/>(ExposureEvents &<br/>ConversionEvents)"]
        ANOM["Anomaly Generator<br/>(5 Labelled Edge Cases)"]
        GT_WRITER["Ground Truth Writer<br/>(data/ground_truth/)"]
        
        GEN --> MD --> AUD --> ASG --> EVT --> ANOM
        ANOM --> GT_WRITER
    end

    subgraph StorageLayer["3. Operational Storage (database/)"]
        DB[(SQLite Database<br/>experiment_analytics.db<br/>11 Operational Tables<br/>FKs & Immutability Triggers)]
    end

    subgraph IsolatedGT["4. External Ground-Truth Benchmark"]
        GT_FILES["data/ground_truth/<br/>ground_truth.csv<br/>ground_truth.json<br/>(External Benchmark Only)"]
    end

    subgraph ServiceLayer["5. Core Services & Analytical Engines (services/)"]
        VAL["Validation Service<br/>(services/validation.py)<br/>Integrity & Business Rules"]
        ANOM_DET["Blind Anomaly Detection<br/>(services/anomaly_detection.py)<br/>SRM, Duplicates, Telemetry"]
        STAT_ENG["Statistical & Decision Engine<br/>(services/statistics.py & metrics.py)<br/>ITT vs Exposed, Z-Test, Welch t-Test,<br/>Newcombe CI, 8-Priority Decision"]
        GRD_ENG["Guardrail Evaluator<br/>(services/guardrails.py)<br/>Breach & Sufficiency Gates"]
        GT_EVAL["Ground-Truth Evaluator<br/>(services/ground_truth_evaluator.py)<br/>Precision, Recall, Coverage"]
    end

    subgraph ExportLayer["6. Canonical Export Engine (exports/)"]
        EXP["exports/export_data.py & report_generator.py<br/>Canonical CSV, JSON, seed_data.sql<br/>SHA-256 Manifest (validation_summary.json)<br/>Executive Report (.md)"]
        EXP_OUT["data/starter/ & data/full/<br/>24 Export Artifacts"]
    end

    subgraph PresentationLayer["7. User Interface (app.py)"]
        UI["Streamlit Interactive Dashboard (9 Pages)<br/>http://localhost:8501"]
    end

    %% Connections
    CFG --> GEN
    MD -.->|Persist| DB
    AUD -.->|Persist| DB
    ASG -.->|Persist| DB
    EVT -.->|Persist| DB
    ANOM -.->|Persist| DB
    GT_WRITER -.->|Write External| GT_FILES

    DB --> VAL
    DB --> ANOM_DET
    ANOM_DET -->|Record Issues| DB
    DB --> STAT_ENG
    DB --> GRD_ENG
    STAT_ENG -->|Record Results| DB
    
    DB -.->|Read Operational| GT_EVAL
    GT_FILES -.->|Read Benchmark| GT_EVAL

    DB --> EXP
    GT_FILES -.->|Include Checksums| EXP
    EXP --> EXP_OUT

    DB <-->|Live Queries & Control| UI
    GEN <-->|Trigger Pipeline| UI
    EXP <-->|Trigger Export| UI
```

## 4. Complete Data Flow Description

1. **Configuration & Seeding (`config/settings.py`)**:
   Execution parameters, schema constants, file paths, and the deterministic seed (`20261022`) are centralized in immutable configuration objects (`STARTER_CONFIG` and `FULL_CONFIG`).

2. **Synthetic Data Generation (`generator/`)**:
   The parameterized 13-step pipeline creates baseline experiments, variants, metric definitions, and user audiences. Eligible users are deterministically randomized into variants. Exposure and conversion telemetry events are simulated, and five controlled anomaly scenarios are injected to exercise edge-case detection.

3. **Operational Persistence (`database/`)**:
   All operational records are written to 11 SQLite tables governed by `database/schema.sql` and SQLAlchemy models in `database/models.py`. Foreign key constraints (`PRAGMA foreign_keys = ON`), partial indexes (e.g. guaranteeing at most one Control variant per experiment), and SQLite triggers prevent illegal lifecycle transitions or tampering with append-only metric definitions and experiment results.

4. **Blind Anomaly Detection (`services/anomaly_detection.py`)**:
   The anomaly detection engine runs exclusively against operational database tables without reading ground-truth benchmark files. It detects Sample Ratio Mismatch (`SRM_DETECTED`), duplicate user assignments (`DUPLICATE_ASSIGNMENT`), exposure order inversions (`EXPOSURE_BEFORE_ASSIGNMENT`), and conversions occurring outside defined conversion windows (`OUTCOME_WINDOW_VIOLATION`), recording findings directly to `experiment_issues`.

5. **Statistical Inference & Decision Hierarchy (`services/statistics.py` & `services/guardrails.py`)**:
   Calculates Intention-to-Treat (ITT) and Exposed-Only metric values. Binary conversion metrics are evaluated using two-proportion z-tests and Newcombe-Wilson 95% confidence intervals, while continuous metrics are evaluated using Welch's t-test. The 8-priority decision engine evaluates guardrail statuses (`PASSED`, `WARNING`, `FAILED`, `INSUFFICIENT_DATA`, `NOT_APPLICABLE`), statistical significance, and practical significance (MDE) to assign deterministic launch recommendations.

6. **Isolated Ground-Truth Evaluation (`services/ground_truth_evaluator.py`)**:
   Once anomaly detection is complete, the ground-truth evaluator performs a strictly read-only comparison between detected issues in `experiment_issues` and external benchmark labels in `data/ground_truth/`, measuring Precision (1.0), Recall (1.0), and Detection Coverage (1.0) with zero database mutations.

7. **Canonical Exports & Manifests (`exports/export_data.py`)**:
   Generates deterministic CSV and JSON exports for all 11 tables, a transactional SQL seed dump (`seed_data.sql`), an executive Markdown evaluation report (`experiment_evaluation_report.md`), and `validation_summary.json` containing live SHA-256 cryptographic checksums for every exported artifact.

8. **Interactive Visualization (`app.py`)**:
   A 9-page Streamlit application connects directly to the SQLite database, rendering portfolio overviews, lifecycle controls, live telemetry diagnostics, statistical outputs, guardrail monitoring, and one-click data export utilities.
