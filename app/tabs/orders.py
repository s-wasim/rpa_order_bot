import streamlit as st
from app.db import get_session
from app.db import Order


def render_orders():
    st.subheader("Placed Orders")

    with get_session() as session:
        orders = session.query(Order).order_by(Order.created_at.desc()).all()

    if not orders:
        st.info("No orders have been placed yet.")
        return

    for order in orders:
        with st.expander(
            f"**{order.demomart_order_no}** — "
            f"${order.total:.2f} — "
            f"{order.created_at.strftime('%Y-%m-%d %H:%M') if order.created_at else 'N/A'}"
        ):
            st.write(f"Run ID: {order.run_id}")
            if order.items:
                item_data = [
                    {
                        "SKU": i.sku or "-",
                        "Product": i.product_title,
                        "Qty": i.qty,
                        "Unit Price": f"${i.unit_price:.2f}",
                        "Total": f"${i.qty * i.unit_price:.2f}",
                    }
                    for i in order.items
                ]
                st.data_editor(
                    item_data,
                    column_config={
                        "SKU": st.column_config.TextColumn("SKU", width="small"),
                        "Product": st.column_config.TextColumn("Product", width="medium"),
                        "Qty": st.column_config.NumberColumn("Qty", width="small"),
                        "Unit Price": st.column_config.TextColumn("Unit Price", width="small"),
                        "Total": st.column_config.TextColumn("Total", width="small"),
                    },
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.caption("No items in this order.")
