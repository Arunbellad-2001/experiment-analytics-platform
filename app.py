"""Streamlit 9-Page Analytical Interface for the Experiment Analytics Platform."""

from __future__ import annotations

import html
import json
import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import func, select

from config.settings import (
    DEFAULT_DB_PATH,
    DEFAULT_RANDOM_SEED,
    FULL_CONFIG,
    FULL_DATA_DIR,
    GROUND_TRUTH_DIR,
    REFERENCE_EPOCH_ISO,
    STARTER_CONFIG,
    STARTER_DATA_DIR,
    DatasetScaleConfig,
    configure_logging,
)
from database.connection import init_db, session_scope
from database.models import (
    Assignment,
    Experiment,
    ExperimentEvent,
    ExperimentIssue,
    ExperimentResult,
    ExposureEvent,
    GuardrailMetric,
    MetricDefinition,
    Variant,
)
from exports.export_data import export_all_datasets
from exports.report_generator import generate_experiment_markdown_report
from generator.pipeline import run_generation_pipeline
from services.experiment_service import (
    transition_experiment_status,
    update_predeclared_parameters,
)
from services.ground_truth_evaluator import evaluate_detections_against_ground_truth
from services.guardrails import evaluate_guardrails_for_variant
from services.metrics import calculate_variant_diagnostics
from services.randomization import validate_randomization_srm
from services.statistics import evaluate_current_launch_decision
from services.validation import run_all_validation_checks

logger = configure_logging()

st.set_page_config(
    page_title="Experiment Analytics Platform",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

TABLE_CSS = """
<style>
.eap-table-wrap {
    overflow-x: auto;
    max-height: 460px;
    overflow-y: auto;
    border: 1px solid rgba(128, 128, 128, 0.25);
    border-radius: 6px;
    margin-bottom: 1rem;
}
table.eap-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.88rem;
}
table.eap-table th {
    position: sticky;
    top: 0;
    background-color: #1e293b;
    color: #f8fafc;
    text-align: left;
    padding: 8px 12px;
    font-weight: 600;
    border-bottom: 2px solid rgba(128, 128, 128, 0.35);
    white-space: nowrap;
}
table.eap-table td {
    padding: 7px 12px;
    border-bottom: 1px solid rgba(128, 128, 128, 0.18);
    white-space: nowrap;
}
table.eap-table tr:hover {
    background-color: rgba(100, 116, 139, 0.12);
}
</style>
"""


def render_table(df: pd.DataFrame) -> None:
    """Render a Pandas DataFrame as a responsive scrollable table without importing pyarrow."""
    if df.empty:
        st.info("No records to display.")
        return

    headers = "".join(f"<th>{html.escape(str(col))}</th>" for col in df.columns)
    body_rows = []
    for _, row in df.iterrows():
        cells = []
        for val in row:
            if pd.isna(val):
                cell_str = "NULL"
            elif isinstance(val, float):
                cell_str = f"{val:.6f}".rstrip("0").rstrip(".") if abs(val) >= 1e-4 or val == 0 else f"{val:.4e}"
            else:
                cell_str = str(val)
            cells.append(f"<td>{html.escape(cell_str)}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")

    table_html = (
        f"{TABLE_CSS}"
        f"<div class='eap-table-wrap'>"
        f"<table class='eap-table'>"
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        f"</table></div>"
    )
    st.markdown(table_html, unsafe_allow_html=True)


@st.cache_resource
def get_initialized_engine():
    """Initialize SQLite schema and bootstrap Starter dataset if the database is empty."""
    engine = init_db(db_path=DEFAULT_DB_PATH)
    with session_scope(engine) as session:
        exp_count = session.scalar(select(func.count(Experiment.experiment_id))) or 0
    if exp_count == 0:
        logger.info("Bootstrapping default Starter dataset on initial startup...")
        run_generation_pipeline(engine, config=STARTER_CONFIG, inject_anomalies=True)
    return engine


def _load_experiments_df(session) -> pd.DataFrame:
    exps = list(
        session.scalars(
            select(Experiment).order_by(Experiment.experiment_id.asc())
        ).all()
    )
    rows = []
    for e in exps:
        live_dec = evaluate_current_launch_decision(session, e.experiment_id)
        trt_dec = live_dec.get(f"VAR-{e.experiment_id}-B", "PENDING")
        rows.append(
            {
                "experiment_id": e.experiment_id,
                "experiment_name": e.experiment_name,
                "experiment_status": e.experiment_status,
                "primary_metric_code": e.primary_metric_code,
                "minimum_detectable_effect": e.minimum_detectable_effect,
                "significance_level": e.significance_level,
                "expected_allocation_ratio": e.expected_allocation_ratio,
                "conversion_window_days": e.conversion_window_days,
                "live_decision": trt_dec,
                "start_date": e.start_date,
                "end_date": e.end_date,
            }
        )
    return pd.DataFrame(rows)


def render_page_1_overview(engine) -> None:
    st.title("Page 1: Portfolio Overview Dashboard")
    st.caption(
        "Live portfolio telemetry, experiment status breakdown, and anomaly summary retrieved directly from SQLite."
    )

    with session_scope(engine) as session:
        val = run_all_validation_checks(session)
        counts = val["entity_counts"]
        df_exp = _load_experiments_df(session)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Experiments", f"{counts['experiments']:,}")
    c2.metric("Audience Members", f"{counts['audience_members']:,}")
    c3.metric("Assignments", f"{counts['assignments']:,}")
    c4.metric("Exposure Events", f"{counts['exposure_events']:,}")
    c5.metric("Conversion Events", f"{counts['conversion_events']:,}")
    c6.metric("Detected Anomalies", f"{counts['experiment_issues']:,}")

    if not df_exp.empty:
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Experiment Lifecycle Status Distribution")
            status_counts = (
                df_exp.groupby("experiment_status", as_index=False)
                .size()
                .rename(columns={"size": "count"})
            )
            fig_status = px.bar(
                status_counts,
                x="experiment_status",
                y="count",
                color="experiment_status",
                text_auto=True,
            )
            st.plotly_chart(fig_status, use_container_width=True)

        with col_b:
            st.subheader("Live Launch Decision Breakdown")
            dec_counts = (
                df_exp.groupby("live_decision", as_index=False)
                .size()
                .rename(columns={"size": "count"})
            )
            fig_dec = px.pie(
                dec_counts,
                names="live_decision",
                values="count",
                hole=0.4,
            )
            st.plotly_chart(fig_dec, use_container_width=True)

        st.subheader("Experiment Portfolio Registry")
        render_table(df_exp)


def render_page_2_experiment_management(engine) -> None:
    st.title("Page 2: Experiment Management & Lifecycle Governance")
    st.caption(
        "Create new experiments, configure variants, metrics, and guardrails, and manage forward lifecycle transitions."
    )

    tab_view, tab_create, tab_lifecycle = st.tabs(
        [
            "Inspect Experiments & Audit History",
            "Create New Experiment",
            "Lifecycle & Predeclared Parameter Controls",
        ]
    )

    with session_scope(engine) as session:
        df_exp = _load_experiments_df(session)
        exp_ids = df_exp["experiment_id"].tolist() if not df_exp.empty else []

        with tab_view:
            if exp_ids:
                sel_exp = st.selectbox(
                    "Select Experiment to Inspect", exp_ids, key="mgmt_sel"
                )
                exp_obj = session.get(Experiment, sel_exp)
                st.markdown(f"**Hypothesis:** {exp_obj.hypothesis}")
                st.markdown(f"**Description:** {exp_obj.description}")

                vars_list = list(
                    session.scalars(
                        select(Variant).where(Variant.experiment_id == sel_exp)
                    ).all()
                )
                st.markdown("#### Configured Variants")
                render_table(
                    pd.DataFrame(
                        [
                            {
                                "variant_id": v.variant_id,
                                "variant_name": v.variant_name,
                                "variant_type": v.variant_type,
                                "allocation_percentage": v.allocation_percentage,
                                "description": v.description,
                            }
                            for v in vars_list
                        ]
                    )
                )

                mets_list = list(
                    session.scalars(
                        select(MetricDefinition)
                        .where(MetricDefinition.experiment_id == sel_exp)
                        .order_by(
                            MetricDefinition.metric_code.asc(),
                            MetricDefinition.metric_version.asc(),
                        )
                    ).all()
                )
                st.markdown("#### Versioned Metric Definitions (Append-Only)")
                render_table(
                    pd.DataFrame(
                        [
                            {
                                "metric_id": m.metric_id,
                                "metric_code": m.metric_code,
                                "metric_version": m.metric_version,
                                "metric_name": m.metric_name,
                                "metric_type": m.metric_type,
                                "calculation_method": m.calculation_method,
                                "effective_from": m.effective_from,
                            }
                            for m in mets_list
                        ]
                    )
                )

                evts_list = list(
                    session.scalars(
                        select(ExperimentEvent)
                        .where(ExperimentEvent.experiment_id == sel_exp)
                        .order_by(ExperimentEvent.event_id.asc())
                    ).all()
                )
                st.markdown("#### Lifecycle State-Change Audit Log")
                render_table(
                    pd.DataFrame(
                        [
                            {
                                "event_id": ev.event_id,
                                "event_type": ev.event_type,
                                "from_status": ev.from_status,
                                "to_status": ev.to_status,
                                "actor": ev.actor,
                                "event_timestamp": ev.event_timestamp,
                                "notes": ev.notes,
                            }
                            for ev in evts_list
                        ]
                    )
                )

        with tab_create:
            with st.form("create_experiment_form"):
                next_idx = len(exp_ids) + 1
                new_exp_id = st.text_input(
                    "Experiment ID", value=f"EXP-2026-{next_idx:06d}"
                )
                new_name = st.text_input(
                    "Experiment Name", value="Simplified Checkout Address Autocomplete"
                )
                new_desc = st.text_area(
                    "Description",
                    value="Tests postal code address autocomplete during checkout.",
                )
                new_hyp = st.text_area(
                    "Hypothesis",
                    value="Address autocomplete increases checkout conversion by at least 2.0 percentage points.",
                )
                c1, c2, c3 = st.columns(3)
                new_metric_type = c1.selectbox(
                    "Primary Metric Type", ["Primary_Binary", "Primary_Continuous"]
                )
                new_mde = c2.number_input(
                    "Predeclared MDE",
                    min_value=0.0,
                    max_value=1.0 if new_metric_type == "Primary_Binary" else 10000.0,
                    value=0.02,
                    step=0.005,
                    format="%.4f",
                )
                new_alpha = c3.number_input(
                    "Significance Level (alpha)",
                    min_value=0.001,
                    max_value=0.20,
                    value=0.05,
                    step=0.005,
                    format="%.3f",
                )
                c4, c5, c6 = st.columns(3)
                ctrl_pct = c4.number_input(
                    "Control (A) Allocation %",
                    min_value=5.0,
                    max_value=95.0,
                    value=50.0,
                    step=5.0,
                )
                trt_pct = 100.0 - ctrl_pct
                c5.metric("Treatment (B) Allocation %", f"{trt_pct:.1f}%")
                conv_win = c6.number_input(
                    "Conversion Window (Days)", min_value=1, max_value=90, value=7
                )
                grd_thresh = st.number_input(
                    "Refund Rate Critical Guardrail Max Increase",
                    min_value=0.001,
                    max_value=0.20,
                    value=0.010,
                    step=0.002,
                    format="%.4f",
                )
                submitted = st.form_submit_button("Create Draft Experiment")

                if submitted:
                    try:
                        p_code = f"MET-{new_exp_id}-CONV"
                        calc_m = (
                            "ITT_Proportion"
                            if new_metric_type == "Primary_Binary"
                            else "ITT_Mean_Value"
                        )
                        exp_new = Experiment(
                            experiment_id=new_exp_id,
                            experiment_name=new_name,
                            description=new_desc,
                            hypothesis=new_hyp,
                            primary_metric_code=p_code,
                            minimum_detectable_effect=float(new_mde),
                            significance_level=float(new_alpha),
                            experiment_status="Draft",
                            expected_allocation_ratio=f"{int(ctrl_pct)}:{int(trt_pct)}",
                            start_date="2026-01-01T00:00:00Z",
                            end_date="2026-01-31T23:59:59Z",
                            conversion_window_days=int(conv_win),
                            random_seed=DEFAULT_RANDOM_SEED,
                            created_at=REFERENCE_EPOCH_ISO,
                            updated_at=REFERENCE_EPOCH_ISO,
                        )
                        var_a = Variant(
                            variant_id=f"VAR-{new_exp_id}-A",
                            experiment_id=new_exp_id,
                            variant_name="A",
                            variant_type="Control",
                            allocation_percentage=float(ctrl_pct),
                            description="Control baseline",
                            created_at=REFERENCE_EPOCH_ISO,
                        )
                        var_b = Variant(
                            variant_id=f"VAR-{new_exp_id}-B",
                            experiment_id=new_exp_id,
                            variant_name="B",
                            variant_type="Treatment",
                            allocation_percentage=float(trt_pct),
                            description="Treatment candidate",
                            created_at=REFERENCE_EPOCH_ISO,
                        )
                        met_primary = MetricDefinition(
                            metric_id=f"{p_code}-V1",
                            experiment_id=new_exp_id,
                            metric_code=p_code,
                            metric_name="Primary Outcome Metric",
                            metric_type=new_metric_type,
                            metric_description="Primary experiment evaluation metric",
                            numerator_definition="Valid conversions in window",
                            denominator_definition="Total eligible assigned users",
                            calculation_method=calc_m,
                            metric_version=1,
                            effective_from=REFERENCE_EPOCH_ISO,
                            created_at=REFERENCE_EPOCH_ISO,
                        )
                        ref_code = f"MET-{new_exp_id}-REFUND"
                        met_ref = MetricDefinition(
                            metric_id=f"{ref_code}-V1",
                            experiment_id=new_exp_id,
                            metric_code=ref_code,
                            metric_name="Refund Rate",
                            metric_type="Guardrail_Rate",
                            metric_description="Refund guardrail rate",
                            numerator_definition="Refund events",
                            denominator_definition="Total eligible assigned users",
                            calculation_method="ITT_Proportion",
                            metric_version=1,
                            effective_from=REFERENCE_EPOCH_ISO,
                            created_at=REFERENCE_EPOCH_ISO,
                        )
                        grd_obj = GuardrailMetric(
                            guardrail_id=f"GRD-{new_exp_id}-01",
                            experiment_id=new_exp_id,
                            metric_id=f"{ref_code}-V1",
                            metric_version=1,
                            guardrail_name="Refund Rate Critical Guardrail",
                            threshold_type="Absolute_Diff",
                            threshold_value=float(grd_thresh),
                            comparison_direction="MAX_INCREASE",
                            severity="CRITICAL",
                            created_at=REFERENCE_EPOCH_ISO,
                        )
                        evt_obj = ExperimentEvent(
                            event_id=f"EVT-{new_exp_id}-001",
                            experiment_id=new_exp_id,
                            event_type="Experiment_Created",
                            from_status=None,
                            to_status="Draft",
                            actor="Data_Analyst",
                            notes="Created via Experiment Management UI",
                            event_timestamp=REFERENCE_EPOCH_ISO,
                        )
                        session.add(exp_new)
                        session.flush()
                        session.add_all([var_a, var_b, met_primary, met_ref])
                        session.flush()
                        session.add_all([grd_obj, evt_obj])
                        session.commit()
                        st.success(f"Created experiment `{new_exp_id}` in Draft status.")
                        st.rerun()
                    except Exception as exc:
                        session.rollback()
                        st.error(f"Could not create experiment: {exc}")

        with tab_lifecycle:
            if exp_ids:
                lc_exp_id = st.selectbox(
                    "Select Experiment", exp_ids, key="lc_exp_select"
                )
                lc_exp = session.get(Experiment, lc_exp_id)
                st.info(
                    f"Current Status: **`{lc_exp.experiment_status}`** | "
                    f"Predeclared MDE: `{lc_exp.minimum_detectable_effect}` | "
                    f"Alpha: `{lc_exp.significance_level}`"
                )

                col_tr, col_mde = st.columns(2)
                with col_tr:
                    st.markdown("#### Transition Lifecycle State")
                    target_st = st.selectbox(
                        "Target Lifecycle State",
                        ["Draft", "Ready", "Running", "Paused", "Completed", "Archived"],
                    )
                    actor_name = st.selectbox(
                        "Actor", ["Data_Analyst", "Marketing_Ops", "System_Admin"]
                    )
                    if st.button("Execute State Transition"):
                        try:
                            transition_experiment_status(
                                session,
                                experiment_id=lc_exp_id,
                                target_status=target_st,
                                actor=actor_name,
                                event_timestamp="2026-01-28T00:00:00Z",
                            )
                            session.commit()
                            st.success(
                                f"Transitioned `{lc_exp_id}` to `{target_st}`."
                            )
                            st.rerun()
                        except Exception as exc:
                            session.rollback()
                            st.error(f"Transition rejected: {exc}")

                with col_mde:
                    st.markdown("#### Update Predeclared MDE (Allowed in Draft Only)")
                    upd_mde = st.number_input(
                        "New MDE Value",
                        min_value=0.0,
                        value=float(lc_exp.minimum_detectable_effect),
                        step=0.005,
                        format="%.4f",
                    )
                    if st.button("Update Predeclared MDE"):
                        try:
                            update_predeclared_parameters(
                                session,
                                experiment_id=lc_exp_id,
                                minimum_detectable_effect=float(upd_mde),
                            )
                            session.commit()
                            st.success(f"Updated MDE for `{lc_exp_id}` to `{upd_mde}`.")
                            st.rerun()
                        except Exception as exc:
                            session.rollback()
                            st.error(f"Parameter lock enforced: {exc}")


def render_page_3_data_generation(engine) -> None:
    st.title("Page 3: Synthetic Data Generation Engine")
    st.caption(
        "Run the deterministic 13-step synthetic generator in Starter mode (2,500 eligible users / 5 experiments) "
        "or Full mode (50,000 eligible users / 10 experiments) with fixed seed 20261022."
    )

    with st.form("generator_controls_form"):
        c1, c2, c3 = st.columns(3)
        preset = c1.radio(
            "Dataset Scale Preset",
            [
                "Starter Mode (2,500 Eligible / 5 Exps)",
                "Full Mode (50,000 Eligible / 10 Exps)",
                "Custom Scale",
            ],
        )
        seed_val = c2.number_input(
            "Deterministic Random Seed", value=DEFAULT_RANDOM_SEED, step=1
        )
        inject_anom = c3.checkbox(
            "Inject All 5 Labelled Anomaly Scenarios (Step 11)", value=True
        )

        c4, c5 = st.columns(2)
        custom_exps = c4.number_input(
            "Custom Experiment Count (if Custom Scale)", min_value=5, max_value=20, value=5
        )
        custom_users = c5.number_input(
            "Custom Eligible Users per Experiment (if Custom Scale)",
            min_value=100,
            max_value=10000,
            value=500,
            step=100,
        )
        run_btn = st.form_submit_button("Run 13-Step Synthetic Data Pipeline")

    if run_btn:
        if preset.startswith("Starter"):
            cfg = DatasetScaleConfig(
                mode_name="starter",
                experiment_count=STARTER_CONFIG.experiment_count,
                eligible_users_per_experiment=STARTER_CONFIG.eligible_users_per_experiment,
                ineligible_users_per_experiment=STARTER_CONFIG.ineligible_users_per_experiment,
                random_seed=int(seed_val),
            )
        elif preset.startswith("Full"):
            cfg = DatasetScaleConfig(
                mode_name="full",
                experiment_count=FULL_CONFIG.experiment_count,
                eligible_users_per_experiment=FULL_CONFIG.eligible_users_per_experiment,
                ineligible_users_per_experiment=FULL_CONFIG.ineligible_users_per_experiment,
                random_seed=int(seed_val),
            )
        else:
            cfg = DatasetScaleConfig(
                mode_name="custom",
                experiment_count=int(custom_exps),
                eligible_users_per_experiment=int(custom_users),
                ineligible_users_per_experiment=max(10, int(custom_users) // 10),
                random_seed=int(seed_val),
            )

        with st.spinner(
            f"Executing 13-step deterministic pipeline ({cfg.total_eligible_users:,} eligible users across {cfg.experiment_count} experiments)..."
        ):
            summary = run_generation_pipeline(
                engine, config=cfg, inject_anomalies=inject_anom
            )

        st.success(
            f"Completed `{summary.mode_name}` pipeline with seed `{summary.random_seed}`!"
        )
        st.json(
            {
                "mode": summary.mode_name,
                "random_seed": summary.random_seed,
                "entity_row_counts": summary.entity_counts,
                "ground_truth_summary": summary.ground_truth_summary,
            }
        )


def render_page_4_randomization_validation(engine) -> None:
    st.title("Page 4: Randomization & Sample Ratio Mismatch (SRM) Validation")
    st.caption(
        "Chi-square goodness-of-fit test comparing expected vs. actual variant traffic allocation."
    )

    with session_scope(engine) as session:
        exps = list(
            session.scalars(
                select(Experiment).order_by(Experiment.experiment_id.asc())
            ).all()
        )
        srm_rows = []
        detail_rows = []
        for exp in exps:
            res = validate_randomization_srm(session, exp.experiment_id)
            srm_rows.append(
                {
                    "experiment_id": exp.experiment_id,
                    "experiment_name": exp.experiment_name,
                    "expected_ratio": exp.expected_allocation_ratio,
                    "total_assigned": res.total_assigned,
                    "chi2_statistic": res.chi2_statistic,
                    "srm_p_value": res.srm_p_value,
                    "srm_alpha": res.srm_alpha,
                    "srm_detected": res.srm_detected,
                    "validation_status": res.validation_status,
                }
            )
            for vs in res.variant_summaries:
                detail_rows.append(
                    {
                        "experiment_id": exp.experiment_id,
                        "variant_id": vs.variant_id,
                        "variant_name": vs.variant_name,
                        "variant_type": vs.variant_type,
                        "expected_pct": vs.expected_percentage,
                        "actual_pct": vs.actual_percentage,
                        "expected_count": vs.expected_count,
                        "actual_count": vs.actual_count,
                        "abs_pct_diff": vs.absolute_percentage_diff,
                    }
                )

    df_srm = pd.DataFrame(srm_rows)
    df_det = pd.DataFrame(detail_rows)

    st.subheader("Portfolio SRM Validation Summary")
    render_table(df_srm)

    st.subheader("Variant Expected vs. Actual Allocation Breakdown")
    fig = px.bar(
        df_det,
        x="experiment_id",
        y=["expected_count", "actual_count"],
        barmode="group",
        facet_col="variant_name",
        title="Expected vs. Actual Sample Counts by Experiment and Variant",
    )
    st.plotly_chart(fig, use_container_width=True)
    render_table(df_det)


def render_page_5_event_analytics(engine) -> None:
    st.title("Page 5: Exposure & Conversion Telemetry Analytics")
    st.caption(
        "Detailed breakdown of exposure events, conversion events, missing telemetry, noncompliance, delayed conversions, and invalid event ordering."
    )

    with session_scope(engine) as session:
        exps = list(
            session.scalars(
                select(Experiment).order_by(Experiment.experiment_id.asc())
            ).all()
        )
        rows = []
        for exp in exps:
            diags = calculate_variant_diagnostics(session, exp.experiment_id)
            invalid_order_cnt = (
                session.scalar(
                    select(func.count(ExposureEvent.exposure_id))
                    .join(
                        Assignment,
                        ExposureEvent.assignment_id == Assignment.assignment_id,
                    )
                    .where(
                        ExposureEvent.experiment_id == exp.experiment_id,
                        ExposureEvent.exposure_timestamp < Assignment.assigned_at,
                    )
                )
                or 0
            )
            for vid, d in diags.items():
                rows.append(
                    {
                        "experiment_id": d.experiment_id,
                        "variant_id": vid,
                        "variant_name": d.variant_name,
                        "variant_type": d.variant_type,
                        "eligible_assigned": d.total_eligible_assigned_users,
                        "exposed_users": d.total_exposed_users,
                        "conversions": d.total_conversions,
                        "missing_telemetry": d.missing_telemetry_count,
                        "noncompliance": d.noncompliance_count,
                        "delayed_conversions": d.delayed_conversion_count,
                        "outside_window_conversions": d.outside_window_conversion_count,
                        "invalid_event_ordering": int(invalid_order_cnt),
                    }
                )

    df_evt = pd.DataFrame(rows)
    st.subheader("Variant Telemetry & Noncompliance Summary")
    render_table(df_evt)

    fig = px.bar(
        df_evt,
        x="variant_id",
        y=[
            "missing_telemetry",
            "noncompliance",
            "delayed_conversions",
            "outside_window_conversions",
            "invalid_event_ordering",
        ],
        barmode="stack",
        title="Telemetry Exceptions, Noncompliance & Delayed Events per Variant",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_page_6_experiment_results(engine) -> None:
    st.title("Page 6: Statistical Inference & Experiment Results")
    st.caption(
        "Control vs. Treatment evaluation featuring pooled two-proportion z-tests, Newcombe-Wilson 95% confidence intervals, "
        "continuous Welch t-tests, Intention-to-Treat (ITT) vs. Exposed Secondary analysis, and the 8-priority Launch Decision Engine."
    )

    method_filter = st.radio(
        "Select Analysis Population Method",
        ["ITT", "EXPOSED_SECONDARY"],
        horizontal=True,
    )

    with session_scope(engine) as session:
        results = list(
            session.scalars(
                select(ExperimentResult)
                .where(ExperimentResult.analysis_method == method_filter)
                .order_by(
                    ExperimentResult.experiment_id.asc(),
                    ExperimentResult.analysis_run_id.desc(),
                    ExperimentResult.variant_id.asc(),
                )
            ).all()
        )
        rows = []
        for r in results:
            live_decs = evaluate_current_launch_decision(session, r.experiment_id)
            rows.append(
                {
                    "result_id": r.result_id,
                    "analysis_run_id": r.analysis_run_id,
                    "experiment_id": r.experiment_id,
                    "variant_id": r.variant_id,
                    "metric_version": r.metric_version,
                    "analysis_method": r.analysis_method,
                    "sample_size": r.sample_size,
                    "numerator": r.numerator,
                    "denominator": r.denominator,
                    "metric_value": r.metric_value,
                    "treatment_effect": r.treatment_effect,
                    "relative_lift": r.relative_lift,
                    "standard_error": r.standard_error,
                    "ci_lower_95": r.confidence_interval_lower,
                    "ci_upper_95": r.confidence_interval_upper,
                    "p_value": r.p_value,
                    "stat_sig": r.statistical_significance,
                    "guardrail_status": r.guardrail_status,
                    "snapshot_decision": r.decision_status,
                    "live_decision": live_decs.get(r.variant_id, r.decision_status),
                }
            )

    df_res = pd.DataFrame(rows)
    render_table(df_res)

    df_trt = df_res[df_res["treatment_effect"].notna()].copy()
    if not df_trt.empty:
        st.subheader("Treatment Effect & 95% Confidence Intervals")
        df_trt["err_plus"] = df_trt["ci_upper_95"] - df_trt["treatment_effect"]
        df_trt["err_minus"] = df_trt["treatment_effect"] - df_trt["ci_lower_95"]
        fig = px.scatter(
            df_trt,
            x="experiment_id",
            y="treatment_effect",
            color="live_decision",
            error_y="err_plus",
            error_y_minus="err_minus",
            hover_data=[
                "analysis_run_id",
                "p_value",
                "relative_lift",
                "guardrail_status",
            ],
            title=f"Treatment Effect with 95% Confidence Intervals ({method_filter})",
        )
        fig.add_hline(y=0.0, line_dash="dash", line_color="gray")
        st.plotly_chart(fig, use_container_width=True)


def render_page_7_guardrail_monitoring(engine) -> None:
    st.title("Page 7: Guardrail Safety Monitoring")
    st.caption(
        "Evaluates Refund Rate, Payment Failure Rate, and Customer Complaint Rate against Warning and Critical thresholds."
    )

    with session_scope(engine) as session:
        exps = list(
            session.scalars(
                select(Experiment).order_by(Experiment.experiment_id.asc())
            ).all()
        )
        exp_ids = [e.experiment_id for e in exps]
        sel_exp = st.selectbox(
            "Filter by Experiment (or choose All)", ["ALL"] + exp_ids
        )

        target_exps = (
            exps
            if sel_exp == "ALL"
            else [e for e in exps if e.experiment_id == sel_exp]
        )
        rows = []
        for exp in target_exps:
            trt_var_id = f"VAR-{exp.experiment_id}-B"
            agg_status, items = evaluate_guardrails_for_variant(
                session, exp.experiment_id, trt_var_id
            )
            for item in items:
                rows.append(
                    {
                        "experiment_id": exp.experiment_id,
                        "guardrail_id": item.guardrail_id,
                        "guardrail_name": item.guardrail_name,
                        "metric_name": item.metric_name,
                        "severity": item.severity,
                        "control_value": item.control_value,
                        "treatment_value": item.treatment_value,
                        "difference": item.difference,
                        "threshold_value": item.threshold_value,
                        "evaluation_status": item.evaluation_status,
                        "aggregate_experiment_status": agg_status,
                        "explanation": item.explanation,
                    }
                )

    df_grd = pd.DataFrame(rows)
    render_table(df_grd)

    if not df_grd.empty:
        fig = px.bar(
            df_grd,
            x="guardrail_id",
            y=["control_value", "treatment_value"],
            barmode="group",
            color_discrete_sequence=["#4C78A8", "#F58518"],
            title="Control vs. Treatment Guardrail Rates",
        )
        st.plotly_chart(fig, use_container_width=True)


def render_page_8_anomaly_and_ground_truth(engine) -> None:
    st.title("Page 8: Anomaly Detection & Blind Ground-Truth Evaluation")
    st.caption(
        "Compares blind operational anomaly detections (`experiment_issues`) against external ground-truth scenario files (`data/ground_truth/`)."
    )

    with session_scope(engine) as session:
        issues = list(
            session.scalars(
                select(ExperimentIssue).order_by(ExperimentIssue.issue_id.asc())
            ).all()
        )
        df_issues = pd.DataFrame(
            [
                {
                    "issue_id": i.issue_id,
                    "experiment_id": i.experiment_id,
                    "issue_type": i.issue_type,
                    "severity": i.severity,
                    "affected_entity": i.affected_entity,
                    "affected_record_id": i.affected_record_id,
                    "detected_at": i.detected_at,
                    "expected_behavior": i.expected_behavior,
                    "actual_behavior": i.actual_behavior,
                    "resolution_status": i.resolution_status,
                }
                for i in issues
            ]
        )

        gt_eval = evaluate_detections_against_ground_truth(session)
        val_summary = run_all_validation_checks(session)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Expected Anomalies", gt_eval.total_expected_anomalies)
    c2.metric("Detected Anomalies", gt_eval.total_detected_anomalies)
    c3.metric("True Positives (TP)", gt_eval.true_positives)
    c4.metric("False Positives (FP)", gt_eval.false_positives)
    c5.metric("Precision", f"{gt_eval.precision * 100:.1f}%")
    c6.metric("Recall & Coverage", f"{gt_eval.recall * 100:.1f}%")

    st.subheader("Ground-Truth Scenario vs. Operational Detection Comparison")
    df_comp = pd.DataFrame(
        [
            {
                "scenario_id": c.scenario_id,
                "experiment_id": c.experiment_id,
                "expected_anomaly_type": c.expected_anomaly_type,
                "affected_entity": c.affected_entity,
                "affected_record_id": c.affected_record_id,
                "detected": c.detected,
                "matched_issue_id": c.matched_issue_id,
                "expected_decision": c.expected_decision,
                "actual_decision": c.actual_decision,
                "decision_matched": c.decision_matched,
                "generation_rule": c.generation_rule,
            }
            for c in gt_eval.scenario_comparisons
        ]
    )
    render_table(df_comp)

    st.subheader(
        "Operational Issues Table (`experiment_issues` — Zero Ground-Truth Columns)"
    )
    render_table(df_issues)

    st.subheader("Automated QA Validation Checks")
    render_table(pd.DataFrame(val_summary["checks"]))


def render_page_9_export_center(engine) -> None:
    st.title("Page 9: Data Export & Reproducibility Center")
    st.caption(
        "Export canonical CSVs, JSONs, SQL seed dumps, executive Markdown reports, and SHA-256 checksum manifests."
    )

    target_folder_choice = st.radio(
        "Select Target Export Folder",
        ["data/starter", "data/full"],
        horizontal=True,
    )
    target_dir = (
        STARTER_DATA_DIR if target_folder_choice == "data/starter" else FULL_DATA_DIR
    )

    if st.button("Generate All Canonical Exports (CSV, JSON, SQL, SHA-256 Manifest)"):
        with session_scope(engine) as session:
            export_all_datasets(
                session, output_dir=target_dir, ground_truth_dir=GROUND_TRUTH_DIR
            )
            md_report = generate_experiment_markdown_report(session)
            (target_dir / "experiment_evaluation_report.md").write_text(
                md_report, encoding="utf-8"
            )
        st.success(f"Exported all datasets and checksum manifest to `{target_dir}`!")

    with session_scope(engine) as session:
        md_report_live = generate_experiment_markdown_report(session)
        val_live = run_all_validation_checks(session)

    col_d1, col_d2 = st.columns(2)
    col_d1.download_button(
        label="Download Executive Evaluation Report (.md)",
        data=md_report_live,
        file_name="experiment_evaluation_report.md",
        mime="text/markdown",
    )
    col_d2.download_button(
        label="Download Live Validation Summary (.json)",
        data=json.dumps(val_live, indent=2, sort_keys=True),
        file_name="validation_summary.json",
        mime="application/json",
    )

    val_summary_file = target_dir / "validation_summary.json"
    if val_summary_file.exists():
        saved_payload = json.loads(val_summary_file.read_text(encoding="utf-8"))
        st.subheader(f"SHA-256 Source Manifest (`{target_folder_choice}`)")
        df_man = pd.DataFrame(saved_payload.get("manifest", []))
        render_table(df_man)

        if not df_man.empty:
            sel_file = st.selectbox(
                "Select Exported File to Download",
                df_man["file_name"].tolist(),
            )
            file_path = target_dir / sel_file
            if file_path.exists():
                st.download_button(
                    label=f"Download {sel_file}",
                    data=file_path.read_bytes(),
                    file_name=sel_file,
                )


def main() -> None:
    engine = get_initialized_engine()

    st.sidebar.title("🧪 Experiment Analytics")
    st.sidebar.markdown("End-to-End A/B Testing & Evaluation Platform")
    pages = {
        "1. Overview Dashboard": render_page_1_overview,
        "2. Experiment Management": render_page_2_experiment_management,
        "3. Data Generation": render_page_3_data_generation,
        "4. Randomization Validation": render_page_4_randomization_validation,
        "5. Event Analytics": render_page_5_event_analytics,
        "6. Experiment Results": render_page_6_experiment_results,
        "7. Guardrail Monitoring": render_page_7_guardrail_monitoring,
        "8. Anomaly & Ground-Truth": render_page_8_anomaly_and_ground_truth,
        "9. Export Center": render_page_9_export_center,
    }
    choice = st.sidebar.radio("Navigation", list(pages.keys()))
    pages[choice](engine)


if __name__ == "__main__":
    main()