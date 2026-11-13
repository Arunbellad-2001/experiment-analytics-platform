"""Markdown and JSON experiment evaluation report and source manifest generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Experiment, ExperimentIssue, ExperimentResult
from services.statistics import evaluate_current_launch_decision


def generate_experiment_markdown_report(session: Session) -> str:
    """Generate a comprehensive Markdown report summarizing all experiments, statistical outcomes, and decisions."""
    experiments = list(
        session.scalars(
            select(Experiment).order_by(Experiment.experiment_id.asc())
        ).all()
    )
    lines: List[str] = [
        "# Experiment Analytics Platform — Executive Evaluation Report",
        "",
        "## 1. Portfolio Decision Summary",
        "",
        "| Experiment ID | Name | Allocation | Primary Metric | Treatment Lift | 95% CI | p-value | Guardrail Status | Live Launch Decision |",
        "| :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :--- |",
    ]

    for exp in experiments:
        live_decisions = evaluate_current_launch_decision(session, exp.experiment_id)
        trt_var_id = f"VAR-{exp.experiment_id}-B"
        live_dec = live_decisions.get(trt_var_id, "PENDING")

        latest_trt_res = session.scalar(
            select(ExperimentResult)
            .where(
                ExperimentResult.experiment_id == exp.experiment_id,
                ExperimentResult.variant_id == trt_var_id,
                ExperimentResult.analysis_method == "ITT",
            )
            .order_by(
                ExperimentResult.analysis_timestamp.desc(),
                ExperimentResult.analysis_run_id.desc(),
            )
            .limit(1)
        )

        if latest_trt_res is not None and latest_trt_res.treatment_effect is not None:
            lift_str = f"{latest_trt_res.treatment_effect:+.4f}"
            ci_str = f"[{latest_trt_res.confidence_interval_lower:+.4f}, {latest_trt_res.confidence_interval_upper:+.4f}]"
            p_str = f"{latest_trt_res.p_value:.4e}"
            grd_str = latest_trt_res.guardrail_status
        else:
            lift_str = "N/A"
            ci_str = "N/A"
            p_str = "N/A"
            grd_str = "N/A"

        lines.append(
            f"| `{exp.experiment_id}` | {exp.experiment_name} | `{exp.expected_allocation_ratio}` | "
            f"`{exp.primary_metric_code}` | {lift_str} | {ci_str} | {p_str} | `{grd_str}` | **`{live_dec}`** |"
        )

    lines.extend(["", "## 2. Detected Anomalies & Validation Issues", ""])
    issues = list(
        session.scalars(
            select(ExperimentIssue).order_by(ExperimentIssue.issue_id.asc())
        ).all()
    )
    if not issues:
        lines.append("No anomalies detected.")
    else:
        lines.append(
            "| Issue ID | Experiment ID | Issue Type | Severity | Affected Entity | Affected Record | Description |"
        )
        lines.append("| :--- | :--- | :--- | :---: | :--- | :--- | :--- |")
        for iss in issues:
            lines.append(
                f"| `{iss.issue_id}` | `{iss.experiment_id}` | `{iss.issue_type}` | "
                f"`{iss.severity}` | `{iss.affected_entity}` | `{iss.affected_record_id}` | {iss.description} |"
            )

    return "\n".join(lines) + "\n"


def format_source_manifest_markdown(validation_payload: Dict[str, Any]) -> str:
    """Render documentation/source_manifest.md content from an export payload."""
    manifest_rows: List[Dict[str, Any]] = validation_payload.get("manifest", [])
    lines: List[str] = [
        "# Synthetic Dataset Source Manifest",
        "",
        f"- **Generator Version**: `{validation_payload.get('generator_version', '1.0.0')}`",
        f"- **Fixed Random Seed**: `{validation_payload.get('random_seed', 20261022)}`",
        f"- **Reference Timestamp**: `{validation_payload.get('generation_timestamp', '2026-01-01T00:00:00Z')}`",
        "- **Data Provenance**: 100% Synthetic Controlled PRNG (`numpy.random.PCG64`); zero personal or confidential data.",
        "",
        "## Exported Artifact Checksums (SHA-256)",
        "",
        "| Dataset Name | File Name | Format | Row Count | SHA-256 Checksum |",
        "| :--- | :--- | :---: | ---: | :--- |",
    ]
    for entry in manifest_rows:
        lines.append(
            f"| `{entry['dataset_name']}` | `{entry['file_name']}` | `{entry['export_format']}` | "
            f"{entry['row_count']} | `{entry['sha256_checksum']}` |"
        )
    return "\n".join(lines) + "\n"