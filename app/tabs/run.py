import time
from pathlib import Path

import streamlit as st
from app.db import get_session
from app.db import Run, RunStep


def render_run():
    st.subheader("Run Timeline")

    with get_session() as session:
        runs = session.query(Run).order_by(Run.created_at.desc()).limit(20).all()

    if not runs:
        st.info("No runs yet. Start a reorder from the Inventory tab.")
        return

    run_options = {f"Run #{r.id} ({r.created_at.strftime('%Y-%m-%d %H:%M:%S')})": r.id for r in runs}
    selected_label = st.selectbox("Select Run", list(run_options.keys()), index=0)
    selected_id = run_options[selected_label]

    with get_session() as session:
        run = session.query(Run).filter(Run.id == selected_id).first()
        steps = (
            session.query(RunStep)
            .filter(RunStep.run_id == selected_id)
            .order_by(RunStep.seq)
            .all()
        )

    if not run:
        st.warning("Run not found.")
        return

    if run.plan_json:
        with st.expander("📋 Plan Card", expanded=True):
            plan = run.plan_json
            if isinstance(plan, list):
                for p in plan:
                    sku = p.get("sku", "?")
                    name = p.get("name", "?")
                    qty = p.get("quantity", "?")
                    terms = p.get("search_terms", "?")
                    notes = p.get("notes", "")
                    st.markdown(f"**{name}** ({sku}) — Search: `{terms}`, Qty: {qty}")
                    if notes:
                        st.caption(notes)
            else:
                st.json(plan)

    if not steps:
        st.info("No steps recorded yet.")
        if run.status == "running":
            st.rerun()
        return

    for step in steps:
        status_color = {
            "running": "#6b7280",
            "succeeded": "#16a34a",
            "matched": "#16a34a",
            "skipped": "#d97706",
            "failed": "#dc2626",
        }.get(step.status, "#6b7280")

        cols = st.columns([3, 1, 6])
        with cols[0]:
            st.markdown(f"**{step.label}**")
            st.caption(f"Step {step.seq}")
        with cols[1]:
            st.markdown(
                f"<span style='background:{status_color};color:white;"
                f"padding:2px 8px;border-radius:4px;font-size:0.8rem;'>{step.status}</span>",
                unsafe_allow_html=True,
            )
        with cols[2]:
            if step.detail:
                st.caption(step.detail)
            if step.screenshot_path:
                ss_path = Path(step.screenshot_path)
                if ss_path.exists():
                    cols2 = st.columns([1, 5])
                    with cols2[0]:
                        clicked = st.button(f"📷 View screenshot", key=f"ss_{step.id}")
                    if clicked:
                        @st.dialog("Screenshot", width="large")
                        def show_screenshot(path):
                            st.image(str(path), use_container_width=True)
                        show_screenshot(ss_path)

        st.divider()

    if run.summary_json:
        summary = run.summary_json
        st.subheader("Run Summary")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ordered", summary.get("ordered", 0))
        c2.metric("Skipped", summary.get("skipped", 0))
        c3.metric("Failed", summary.get("failed", 0))
        c4.metric("Total", f"${summary.get('total', 0):.2f}" if summary.get("total") else "$0")
        if summary.get("order_number"):
            st.success(f"Order Number: {summary['order_number']}")

    if run.status == "running":
        time.sleep(2)
        st.rerun()
