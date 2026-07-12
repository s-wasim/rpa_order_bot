import streamlit as st
from app.db import get_session
from app.db import Inventory, Run
from app.graph.runner import run_agent


def render_inventory():
    st.subheader("Inventory Management")

    with get_session() as session:
        items = session.query(Inventory).order_by(Inventory.sku).all()

        data = []
        for item in items:
            is_low = (item.qty + item.on_order) < item.reorder_threshold
            data.append({
                "SKU": item.sku,
                "Name": item.name,
                "Qty": item.qty,
                "Threshold": item.reorder_threshold,
                "Reorder Qty": item.reorder_qty,
                "On Order": item.on_order,
                "_low": is_low,
            })

    low_count = sum(1 for d in data if d["_low"])

    edited = st.data_editor(
        data,
        column_config={
            "SKU": st.column_config.TextColumn("SKU", disabled=True, width="small"),
            "Name": st.column_config.TextColumn("Name", disabled=True, width="medium"),
            "Qty": st.column_config.NumberColumn("Qty", disabled=True, width="small"),
            "Threshold": st.column_config.NumberColumn("Threshold", width="small"),
            "Reorder Qty": st.column_config.NumberColumn("Reorder Qty", width="small"),
            "On Order": st.column_config.NumberColumn("On Order", disabled=True, width="small"),
            "_low": None,
        },
        hide_index=True,
        use_container_width=True,
    )

    for i, row in enumerate(edited):
        if row["_low"]:
            st.markdown(
                f"""
                <style>
                div[data-testid^="stDataFrame"] tbody tr:nth-child({i + 1}) {{
                    background-color: #dc2626 !important;
                    color: white !important;
                }}
                </style>
                """,
                unsafe_allow_html=True,
            )

    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("Save Thresholds", type="secondary"):
            with get_session() as session:
                for row in edited:
                    inv = session.query(Inventory).filter(Inventory.sku == row["SKU"]).first()
                    if inv:
                        inv.reorder_threshold = row["Threshold"]
                        inv.reorder_qty = row["Reorder Qty"]
            st.success("Thresholds saved!")

    with col2:
        run_disabled = low_count == 0
        if st.button("Run Reorder Agent", type="primary", disabled=run_disabled):
            with get_session() as session:
                run = Run(status="running")
                session.add(run)
                session.flush()
                run_id = run.id

            with st.spinner("Running reorder agent..."):
                result = run_agent(run_id)

            if result.get("status") == "succeeded":
                st.success(f"Reorder complete! Ordered: {result.get('ordered', 0)}, "
                           f"Skipped: {result.get('skipped', 0)}, "
                           f"Failed: {result.get('failed', 0)}")
                if result.get("order_number"):
                    st.info(f"Order number: {result['order_number']}")
            else:
                st.warning(f"Reorder skipped: {result.get('reason', 'Unknown')}")

    if low_count == 0:
        st.info("All inventory items are adequately stocked. No reorder needed.")
    else:
        st.warning(f"{low_count} item(s) below reorder threshold.")
