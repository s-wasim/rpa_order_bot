import streamlit as st
from app.db import init_db, seed_inventory

st.set_page_config(page_title="RPA Order Bot", layout="wide")
st.title("RPA Order Bot — AI Browser Automation Demo")

if "db_initialized" not in st.session_state:
    with st.spinner("Initializing database..."):
        init_db()
        from app.db import get_session
        with get_session() as session:
            seed_inventory(session)
    st.session_state.db_initialized = True

tabs = st.tabs(["📦 Inventory", "🤖 Run", "🧾 Orders", "🛒 Storefront"])
with tabs[0]:
    from app.tabs.inventory import render_inventory
    render_inventory()
with tabs[1]:
    from app.tabs.run import render_run
    render_run()
with tabs[2]:
    from app.tabs.orders import render_orders
    render_orders()
with tabs[3]:
    from app.tabs.storefront import render_storefront
    render_storefront()
