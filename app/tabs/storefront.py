import streamlit as st
from app.settings import MOCKSHOP_URL


def render_storefront():
    st.subheader("Storefront")

    local_url = MOCKSHOP_URL.replace("mockshop", "localhost")

    st.markdown(
        """
        DemoMart is a **mock storefront** running alongside the RPA Order Bot.
        It provides a realistic e-commerce interface with search, product pages,
        cart, and checkout — all with `data-testid` attributes for reliable Playwright automation.

        **The pitch:** Same automation, pointed at your vendor with a selector map + auth added.
        """
    )

    st.markdown("### Links")
    st.markdown(f"- [DemoMart Home]({local_url}) — Browse all products")
    st.markdown(f"- [DemoMart Orders]({local_url}/orders) — View placed orders on DemoMart")

    st.markdown("### How it works")
    st.markdown(
        """
        1. **Inventory tab** shows stock levels. Low-stock items are highlighted.
        2. **Run Reorder Agent** triggers the browser automation pipeline.
        3. The bot searches DemoMart, matches products using Claude AI,
           adds to cart, and checks out automatically.
        4. **Orders tab** shows what was placed.
        5. **DemoMart** is the real storefront — you can browse it directly.

        Swap the target URL, map a few selectors, add auth, and point this at any vendor portal.
        """
    )
