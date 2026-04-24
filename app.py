import subprocess
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Feedback Pipeline",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
OUTPUT_DIR = Path("data/output")
INPUT_DIR = Path("data/input")

TICKETS_FILE = OUTPUT_DIR / "generated_tickets.csv"
METRICS_FILE = OUTPUT_DIR / "metrics.csv"
LOG_FILE = OUTPUT_DIR / "processing_log.csv"

VALID_CATEGORIES = ["Bug", "Feature Request", "Praise", "Complaint", "Spam"]
VALID_PRIORITIES = ["Critical", "High", "Medium", "Low"]

CATEGORY_COLORS = {
    "Bug": "#ef4444",
    "Feature Request": "#3b82f6",
    "Praise": "#22c55e",
    "Complaint": "#f97316",
    "Spam": "#9ca3af",
}

PRIORITY_COLORS = {
    "Critical": "#dc2626",
    "High": "#ea580c",
    "Medium": "#ca8a04",
    "Low": "#16a34a",
}


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------
@st.cache_data(ttl=5)
def load_tickets() -> pd.DataFrame:
    if not TICKETS_FILE.exists():
        return pd.DataFrame(columns=[
            "ticket_id", "source_id", "source_type", "title", "description",
            "category", "priority", "technical_details", "created_at",
        ])
    df = pd.read_csv(TICKETS_FILE)
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
    return df


@st.cache_data(ttl=5)
def load_metrics() -> pd.DataFrame:
    if not METRICS_FILE.exists():
        return pd.DataFrame()
    df = pd.read_csv(METRICS_FILE)
    df["run_at"] = pd.to_datetime(df["run_at"], errors="coerce", utc=True)
    return df


@st.cache_data(ttl=5)
def load_log() -> pd.DataFrame:
    if not LOG_FILE.exists():
        return pd.DataFrame()
    df = pd.read_csv(LOG_FILE)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
st.sidebar.title("Feedback Pipeline")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Generate Dummy Data", "Configure & Run", "Tickets", "Analytics"],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
if st.sidebar.button("Refresh data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _kpi(col, label, value, delta=None, delta_color="normal"):
    with col:
        st.metric(label, value, delta=delta, delta_color=delta_color)


# ===========================================================================
# PAGE 1 — Dashboard
# ===========================================================================
if page == "Dashboard":
    st.title("Dashboard")

    tickets = load_tickets()
    metrics = load_metrics()

    # ── KPI row ──────────────────────────────────────────────────────────────
    total = len(tickets)
    bugs = int((tickets["category"] == "Bug").sum()) if total else 0
    features = int((tickets["category"] == "Feature Request").sum()) if total else 0
    critical = int((tickets["priority"] == "Critical").sum()) if total else 0

    last_run = metrics.iloc[-1] if not metrics.empty else None

    c1, c2, c3, c4, c5 = st.columns(5)
    _kpi(c1, "Total Tickets", total)
    _kpi(c2, "Bugs", bugs)
    _kpi(c3, "Feature Requests", features)
    _kpi(c4, "Critical Priority", critical)
    _kpi(c5, "Pipeline Runs", len(metrics))

    st.markdown("---")

    # ── Charts row ───────────────────────────────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Category Breakdown")
        if total:
            cat_counts = tickets["category"].value_counts().reset_index()
            cat_counts.columns = ["Category", "Count"]
            fig = px.pie(
                cat_counts, names="Category", values="Count",
                color="Category",
                color_discrete_map=CATEGORY_COLORS,
                hole=0.4,
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.update_layout(showlegend=False, margin=dict(t=0, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No tickets yet. Run the pipeline to generate tickets.")

    with col_right:
        st.subheader("Priority Distribution")
        if total:
            pri_counts = tickets["priority"].value_counts().reset_index()
            pri_counts.columns = ["Priority", "Count"]
            pri_counts["Priority"] = pd.Categorical(
                pri_counts["Priority"], categories=VALID_PRIORITIES, ordered=True
            )
            pri_counts = pri_counts.sort_values("Priority")
            fig2 = px.bar(
                pri_counts, x="Priority", y="Count",
                color="Priority",
                color_discrete_map=PRIORITY_COLORS,
            )
            fig2.update_layout(showlegend=False, margin=dict(t=0, b=0))
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No tickets yet.")

    st.markdown("---")

    # ── Latest run summary ───────────────────────────────────────────────────
    if last_run is not None:
        st.subheader("Latest Run")
        r1, r2, r3, r4, r5 = st.columns(5)
        _kpi(r1, "Run ID", str(last_run["run_id"]))
        _kpi(r2, "Processed", int(last_run["total_processed"]))
        _kpi(r3, "Created", int(last_run["tickets_created"]))
        _kpi(r4, "Skipped", int(last_run["skipped"]))
        _kpi(r5, "Failed", int(last_run["failed"]))

    st.markdown("---")

    # ── Recent tickets table ─────────────────────────────────────────────────
    st.subheader("Recent Tickets")
    if total:
        recent = tickets.sort_values("created_at", ascending=False).head(10)
        display = recent[["ticket_id", "category", "priority", "source_type", "title", "created_at"]].copy()
        display["created_at"] = display["created_at"].dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(display, use_container_width=True, hide_index=True)
    else:
        st.info("No tickets generated yet.")


# ===========================================================================
# PAGE 2 — Generate Dummy Data
# ===========================================================================
elif page == "Generate Dummy Data":
    st.title("Generate Dummy Data")
    st.markdown(
        "Produce realistic seed data for the feedback pipeline. "
        "Files are written to **`data/input/`**."
    )
    st.markdown("---")

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.subheader("Settings")

        n_reviews = st.number_input(
            "App Reviews",
            min_value=10, max_value=1000, value=120, step=10,
            help="Number of app store reviews to generate.",
        )
        n_emails = st.number_input(
            "Support Emails",
            min_value=5, max_value=500, value=60, step=5,
            help="Number of support emails to generate.",
        )
        use_seed = st.checkbox("Fix random seed (reproducible output)")
        seed_val = st.number_input(
            "Seed value", min_value=0, max_value=99999, value=42,
            disabled=not use_seed,
        )

        st.markdown("---")
        st.markdown("**Output preview**")
        st.markdown(
            f"- `app_store_reviews.csv` — **{n_reviews}** rows  \n"
            f"- `support_emails.csv` — **{n_emails}** rows  \n"
            f"- `expected_classifications.csv` — **{n_reviews + n_emails}** rows"
        )

    with col_right:
        st.subheader("Generate")

        existing = [
            (INPUT_DIR / "app_reviews.csv").exists(),
            (INPUT_DIR / "support_emails.csv").exists(),
            (INPUT_DIR / "expected_classifications.csv").exists(),
        ]
        if any(existing):
            st.warning(
                "Existing files in `data/input/` will be overwritten.",
                icon="⚠️",
            )

        generate_clicked = st.button(
            "Generate Dummy Data", type="primary", use_container_width=True
        )

        if generate_clicked:
            cmd = [
                sys.executable, "data-gen/generate.py",
                "--reviews", str(n_reviews),
                "--emails", str(n_emails),
                "--output", "data/input",
            ]
            if use_seed:
                cmd += ["--seed", str(seed_val)]

            with st.spinner("Generating data…"):
                result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                st.success("Data generated successfully.")
            else:
                st.error("Generation failed — see output below.")

            output = result.stdout + (result.stderr or "")
            if output.strip():
                with st.expander("Generator output", expanded=True):
                    st.code(output, language=None)

            st.cache_data.clear()

        st.markdown("---")
        st.subheader("Current Files")

        for fname in ["app_store_reviews.csv", "support_emails.csv", "expected_classifications.csv"]:
            fpath = INPUT_DIR / fname
            if fpath.exists():
                size = fpath.stat().st_size
                df_prev = pd.read_csv(fpath, nrows=0)
                row_count = sum(1 for _ in open(fpath)) - 1
                st.markdown(
                    f"**{fname}** — {row_count} rows, "
                    f"{len(df_prev.columns)} cols, {size / 1024:.1f} KB"
                )
            else:
                st.markdown(f"~~{fname}~~ — not found")


# ===========================================================================
# PAGE 3 — Configure & Run
# ===========================================================================
elif page == "Configure & Run":
    st.title("Configure & Run")

    col_config, col_run = st.columns([1, 1], gap="large")

    # ── Config panel ─────────────────────────────────────────────────────────
    with col_config:
        st.subheader("Classification Settings")

        threshold = st.slider(
            "Confidence Threshold",
            min_value=0.0, max_value=1.0,
            value=float(st.session_state.get("threshold", 0.7)),
            step=0.05,
            help="Items with confidence below this are skipped.",
            key="threshold",
        )

        st.markdown("**Default Priority by Category**")
        default_priorities = st.session_state.get("default_priorities", {
            "Bug": "High",
            "Feature Request": "Medium",
            "Complaint": "Low",
            "Praise": "Low",
            "Spam": "Low",
        })

        new_priorities = {}
        for cat in ["Bug", "Feature Request", "Complaint"]:
            new_priorities[cat] = st.selectbox(
                cat,
                options=VALID_PRIORITIES,
                index=VALID_PRIORITIES.index(default_priorities.get(cat, "Medium")),
                key=f"priority_{cat}",
            )
        new_priorities["Praise"] = "Low"
        new_priorities["Spam"] = "Low"
        st.session_state["default_priorities"] = new_priorities

        st.markdown("---")
        st.subheader("Run Settings")
        limit = st.number_input(
            "Item Limit (0 = all)",
            min_value=0, max_value=500,
            value=int(st.session_state.get("run_limit", 0)),
            key="run_limit",
            help="Limit how many feedback items to process.",
        )

    # ── Run panel ─────────────────────────────────────────────────────────────
    with col_run:
        st.subheader("Run Pipeline")

        st.info(
            f"**Confidence threshold:** {threshold:.2f}  \n"
            f"**Item limit:** {'all' if not limit else limit}  \n"
            f"**Bug priority:** {new_priorities['Bug']}  \n"
            f"**Feature priority:** {new_priorities['Feature Request']}"
        )

        run_clicked = st.button("Run Pipeline", type="primary", use_container_width=True)

        if run_clicked:
            with st.spinner("Pipeline running — this may take a few minutes..."):
                env_overrides = {
                    "PIPELINE_CONFIDENCE_THRESHOLD": str(threshold),
                    "PIPELINE_DEFAULT_PRIORITY_BUG": new_priorities["Bug"],
                    "PIPELINE_DEFAULT_PRIORITY_FEATURE": new_priorities["Feature Request"],
                }
                cmd = [sys.executable, "-m", "pipeline"]
                if limit:
                    cmd = [sys.executable, "pipeline.py", "--limit", str(limit)]
                else:
                    cmd = [sys.executable, "pipeline.py"]

                import os
                run_env = {**os.environ, **env_overrides}
                result = subprocess.run(
                    cmd, capture_output=True, text=True, env=run_env
                )

            if result.returncode == 0:
                st.success("Pipeline completed successfully.")
            else:
                st.error("Pipeline completed with errors.")

            output = result.stdout + (result.stderr or "")
            if output.strip():
                with st.expander("Pipeline output", expanded=True):
                    st.code(output, language=None)

            st.cache_data.clear()

        st.markdown("---")
        st.subheader("Current Config")
        st.json({
            "model": "claude-sonnet-4-6",
            "confidence_threshold": threshold,
            "default_priority": new_priorities,
            "item_limit": limit if limit else "all",
        })


# ===========================================================================
# PAGE 3 — Tickets (Manual Override)
# ===========================================================================
elif page == "Tickets":
    st.title("Tickets")

    tickets = load_tickets()

    if tickets.empty:
        st.info("No tickets found. Run the pipeline first.")
        st.stop()

    # ── Filters ───────────────────────────────────────────────────────────────
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        cat_filter = st.multiselect(
            "Category", VALID_CATEGORIES,
            default=VALID_CATEGORIES,
        )
    with fc2:
        pri_filter = st.multiselect(
            "Priority", VALID_PRIORITIES,
            default=VALID_PRIORITIES,
        )
    with fc3:
        src_filter = st.multiselect(
            "Source", ["review", "email"],
            default=["review", "email"],
        )

    mask = (
        tickets["category"].isin(cat_filter) &
        tickets["priority"].isin(pri_filter) &
        tickets["source_type"].isin(src_filter)
    )
    filtered = tickets[mask].copy()
    st.caption(f"Showing {len(filtered)} of {len(tickets)} tickets")

    st.markdown("---")

    # ── Editable table ────────────────────────────────────────────────────────
    st.subheader("Edit Tickets")

    edited = st.data_editor(
        filtered[[
            "ticket_id", "category", "priority", "source_type",
            "source_id", "title", "technical_details", "created_at",
        ]],
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "ticket_id":        st.column_config.TextColumn("ID", disabled=True, width="small"),
            "category":         st.column_config.SelectboxColumn("Category", options=VALID_CATEGORIES, width="medium"),
            "priority":         st.column_config.SelectboxColumn("Priority", options=VALID_PRIORITIES, width="small"),
            "source_type":      st.column_config.TextColumn("Source", disabled=True, width="small"),
            "source_id":        st.column_config.TextColumn("Src ID", disabled=True, width="small"),
            "title":            st.column_config.TextColumn("Title", width="large"),
            "technical_details":st.column_config.TextColumn("Technical Details", width="large"),
            "created_at":       st.column_config.DatetimeColumn("Created At", disabled=True, width="medium"),
        },
    )

    if st.button("Save changes", type="primary"):
        updated = tickets.copy()
        for _, row in edited.iterrows():
            idx = updated[updated["ticket_id"] == row["ticket_id"]].index
            if not idx.empty:
                updated.loc[idx, "category"] = row["category"]
                updated.loc[idx, "priority"] = row["priority"]
                updated.loc[idx, "title"] = row["title"]
                updated.loc[idx, "technical_details"] = row["technical_details"]
        updated.to_csv(TICKETS_FILE, index=False)
        st.success("Tickets saved.")
        st.cache_data.clear()

    st.markdown("---")

    # ── Ticket detail view ────────────────────────────────────────────────────
    st.subheader("Ticket Detail")

    ticket_ids = filtered["ticket_id"].tolist()
    selected_id = st.selectbox("Select ticket to view/edit description", ticket_ids)

    if selected_id:
        row = tickets[tickets["ticket_id"] == selected_id].iloc[0]

        d1, d2, d3 = st.columns(3)
        d1.markdown(f"**Category:** {row['category']}")
        d2.markdown(f"**Priority:** {row['priority']}")
        d3.markdown(f"**Source:** {row['source_type']} / {row['source_id']}")

        new_title = st.text_input("Title", value=str(row["title"]))
        new_desc = st.text_area("Description", value=str(row["description"]), height=200)
        new_tech = st.text_area("Technical Details", value=str(row.get("technical_details", "")), height=80)

        if st.button("Save this ticket"):
            tickets_all = load_tickets()
            idx = tickets_all[tickets_all["ticket_id"] == selected_id].index
            if not idx.empty:
                tickets_all.loc[idx, "title"] = new_title
                tickets_all.loc[idx, "description"] = new_desc
                tickets_all.loc[idx, "technical_details"] = new_tech
                tickets_all.to_csv(TICKETS_FILE, index=False)
                st.success(f"Ticket {selected_id} saved.")
                st.cache_data.clear()


# ===========================================================================
# PAGE 4 — Analytics
# ===========================================================================
elif page == "Analytics":
    st.title("Analytics")

    metrics = load_metrics()
    log = load_log()
    tickets = load_tickets()

    if metrics.empty:
        st.info("No pipeline runs yet. Run the pipeline to see analytics.")
        st.stop()

    # ── Run history summary ───────────────────────────────────────────────────
    st.subheader("Run History")

    run_display = metrics[[
        "run_id", "run_at", "total_processed", "tickets_created",
        "skipped", "failed",
        "bug_count", "feature_request_count", "spam_count",
    ]].copy()
    run_display["run_at"] = run_display["run_at"].dt.strftime("%Y-%m-%d %H:%M")
    run_display["success_rate"] = (
        run_display["tickets_created"] / run_display["total_processed"] * 100
    ).round(1).astype(str) + "%"

    st.dataframe(run_display, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── Tickets per run chart ─────────────────────────────────────────────────
    ac1, ac2 = st.columns(2)

    with ac1:
        st.subheader("Tickets Created per Run")
        fig_runs = go.Figure()
        fig_runs.add_trace(go.Bar(
            x=list(range(1, len(metrics) + 1)),
            y=metrics["tickets_created"],
            name="Created",
            marker_color="#3b82f6",
        ))
        fig_runs.add_trace(go.Bar(
            x=list(range(1, len(metrics) + 1)),
            y=metrics["skipped"],
            name="Skipped",
            marker_color="#9ca3af",
        ))
        fig_runs.add_trace(go.Bar(
            x=list(range(1, len(metrics) + 1)),
            y=metrics["failed"],
            name="Failed",
            marker_color="#ef4444",
        ))
        fig_runs.update_layout(
            barmode="stack",
            xaxis_title="Run",
            yaxis_title="Items",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(t=30, b=0),
        )
        st.plotly_chart(fig_runs, use_container_width=True)

    with ac2:
        st.subheader("Category Distribution (All Runs)")
        if not tickets.empty:
            cat_all = tickets["category"].value_counts().reset_index()
            cat_all.columns = ["Category", "Count"]
            fig_cat = px.bar(
                cat_all, x="Category", y="Count",
                color="Category", color_discrete_map=CATEGORY_COLORS,
            )
            fig_cat.update_layout(showlegend=False, margin=dict(t=30, b=0))
            st.plotly_chart(fig_cat, use_container_width=True)
        else:
            st.info("No ticket data.")

    st.markdown("---")

    # ── Confidence distribution ───────────────────────────────────────────────
    bc1, bc2 = st.columns(2)

    with bc1:
        st.subheader("Confidence Score Distribution")
        conf_data = log[log["confidence"].notna() & (log["agent"] == "classifier")]
        if not conf_data.empty:
            fig_conf = px.histogram(
                conf_data, x="confidence", nbins=20,
                color_discrete_sequence=["#6366f1"],
                labels={"confidence": "Confidence Score", "count": "Count"},
            )
            fig_conf.add_vline(
                x=0.7, line_dash="dash", line_color="red",
                annotation_text="Threshold (0.7)",
            )
            fig_conf.update_layout(margin=dict(t=30, b=0))
            st.plotly_chart(fig_conf, use_container_width=True)
        else:
            st.info("No classifier confidence data in logs.")

    with bc2:
        st.subheader("Agent Step Counts")
        if not log.empty:
            step_counts = log["agent"].value_counts().reset_index()
            step_counts.columns = ["Agent", "Calls"]
            fig_steps = px.bar(
                step_counts, x="Agent", y="Calls",
                color_discrete_sequence=["#8b5cf6"],
            )
            fig_steps.update_layout(margin=dict(t=30, b=0))
            st.plotly_chart(fig_steps, use_container_width=True)
        else:
            st.info("No agent log data.")

    st.markdown("---")

    # ── Per-category ticket stats ─────────────────────────────────────────────
    st.subheader("Ticket Priority by Category")
    if not tickets.empty:
        cross = pd.crosstab(tickets["category"], tickets["priority"])
        for col in VALID_PRIORITIES:
            if col not in cross.columns:
                cross[col] = 0
        cross = cross[VALID_PRIORITIES]
        fig_cross = px.bar(
            cross.reset_index().melt(id_vars="category", var_name="Priority", value_name="Count"),
            x="category", y="Count", color="Priority",
            color_discrete_map=PRIORITY_COLORS,
            barmode="group",
            labels={"category": "Category"},
        )
        fig_cross.update_layout(margin=dict(t=30, b=0))
        st.plotly_chart(fig_cross, use_container_width=True)

    # ── Aggregate stats ───────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Aggregate Statistics")

    total_processed = int(metrics["total_processed"].sum())
    total_created = int(metrics["tickets_created"].sum())
    total_skipped = int(metrics["skipped"].sum())
    total_failed = int(metrics["failed"].sum())
    overall_rate = round(total_created / total_processed * 100, 1) if total_processed else 0

    s1, s2, s3, s4, s5 = st.columns(5)
    _kpi(s1, "Total Processed", total_processed)
    _kpi(s2, "Total Created", total_created)
    _kpi(s3, "Total Skipped", total_skipped)
    _kpi(s4, "Total Failed", total_failed)
    _kpi(s5, "Overall Success Rate", f"{overall_rate}%")
