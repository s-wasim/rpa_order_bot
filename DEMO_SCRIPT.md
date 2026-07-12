# RPA Order Bot — Demo Script

Follow the TRD §3 flow to demonstrate the full automation pipeline.

---

## Step 1: Open the App

Navigate to [http://localhost:8501](http://localhost:8501).

**Talking points:**
- "This is the RPA Order Bot — an AI-powered browser automation agent that monitors inventory and places replenishment orders automatically."
- "It uses Claude for planning and product matching, LangGraph for orchestration, and Playwright for browser automation."

---

## Step 2: Inventory Tab — 10 SKUs, 3 Red Rows

The Inventory tab loads with the seed data:

| Status | SKU | Item | Qty | Threshold |
|--------|-----|------|-----|-----------|
| 🟢 | USB-C-HUB-002 | USB-C Multiport Hub | 8 | 5 |
| 🔴 | THERMAL-PASTE-001 | Thermal Paste 4g Tube | 2 | 5 |
| 🔴 | MECH-KEYB-003 | Mechanical Keyboard | 1 | 3 |
| 🟢 | HDMI-CABLE-004 | HDMI 2.1 Cable 3m | 15 | 10 |
| 🟢 | MOUSE-PAD-005 | Large Mouse Pad | 8 | 5 |
| 🟢 | SSD-1TB-006 | SSD 1TB Internal | 6 | 3 |
| 🟢 | WEBCAM-007 | 1080p Webcam | 10 | 4 |
| 🔴 | NO-MATCH-008 | Proprietary Connector Kit | 1 | 3 |
| 🟢 | WIRELESS-MOUSe-009 | Wireless Mouse | 8 | 5 |
| 🟢 | USB-MICRO-010 | USB Microphone | 6 | 3 |

Rows where `qty + on_order < reorder_threshold` are highlighted in **red** (`#dc2626`).

**Talking points:**
- "Three items are below their reorder thresholds. The system automatically identifies them."
- "You can edit the Threshold and Reorder Qty columns and click Save."
- "The Run Reorder Agent button is active because low-stock items exist."
- "We're about to watch the agent handle three very different cases: an exact product match, a match with alternatives, and a product that simply doesn't exist on the storefront."

---

## Step 3: Click "Run Reorder Agent"

This triggers `run_scripted()` (Phase 1) or the LangGraph (Phase 2).

**Talking points:**
- "A new Run record is created in the database with status 'running'."
- "The agent spins up a Playwright browser (headless or headed depending on config)."
- "All navigation is guarded — the browser is locked to only talk to the DemoMart origin."
- "Every step is recorded: searches, match decisions, cart operations, checkout."

---

## Step 4: Watch the Run Tab

Switch to the **🤖 Run** tab immediately after clicking Run.

### Plan Card

A plan card appears at the top showing what the agent plans to do:

```
Thermal Paste 4g Tube (THERMAL-PASTE-001) — Search: `thermal paste`, Qty: 10
Mechanical Keyboard (MECH-KEYB-003) — Search: `mechanical keyboard`, Qty: 3
Proprietary Connector Kit (NO-MATCH-008) — Search: `connector kit`, Qty: 3
```

**Talking points:**
- "Claude generates the shopping plan. It decides what search terms to use and how many to order."
- "This is the 'think step' — the LLM reasons about what to buy before the browser moves."

### Browse Loop (3 items, one at a time)

Each item goes through: **Search → Match → Add to Cart (or Skip/Fail)**

**Item 1: Thermal Paste — Exact Match**
```
Search results → Claude picks "ArcticBond TX-4 Thermal Compound, 4 g" ($8.99)
→ Added 10× to cart → status: succeeded
```
- Screenshot shows the search results and the cart confirmation.

**Talking points:**
- "Claude matches the inventory item 'Thermal Paste 4g Tube' to the storefront product 'ArcticBond TX-4 Thermal Compound'."
- "This is a straightforward match — the product name and description align perfectly."
- "10 units are added to the cart based on the reorder quantity."

**Item 2: Mechanical Keyboard — Match with Alternatives**
```
Search results → Claude picks "TypeMaster TKL Mechanical Keyboard, Cherry MX" ($89.99)
→ Added 3× to cart → status: succeeded
```
- The search also returns "Mechanical Switch Sampler Kit" but Claude correctly selects the full keyboard.

**Talking points:**
- "The search returns multiple results. Claude evaluates each candidate against the inventory item's name and picks the best match."
- "This demonstrates the AI handling ambiguous search results — it chose the keyboard, not the switch sampler."

**Item 3: Proprietary Connector Kit — No Match (Skip)**
```
Search results → No matching product found → status: skipped
```
- Reasoning shown in the step detail: "No product on the storefront matches 'Proprietary Connector Kit'"

**Talking points (SKIP CASE — key narrative):**
- "This is the most important case. The inventory has a 'Proprietary Connector Kit' that simply does not exist on DemoMart."
- "Claude returns `choice_index: null` — it refuses to force a bad match."
- "The item is gracefully **skipped**, not failed. The agent moves on."
- "This is the key advantage of AI-driven automation over rule-based scripts. A traditional bot would either crash on a missing element or silently buy the wrong product. Claude says 'I'm not sure, skipping.'"
- "In production, skipped items would trigger an alert for manual review."

### Checkout

After the browse loop, if any items were added to the cart:

```
→ Navigating to checkout
→ Filling form with company details
→ Placing order → Order DM-XXXXX confirmed
```

**Talking points:**
- "The agent navigates to the checkout page, fills the form, and submits."
- "It extracts the DM-XXXXX order number from the confirmation page."
- "A confirmation screenshot is saved."

### Record

The order is recorded in the database:

- `orders` table: order number, total, timestamp
- `order_items` table: each item with SKU, product title, quantity, unit price
- `inventory` table: `on_order` incremented for matched items
- `run` status updated to `succeeded` with summary JSON

---

## Step 5: Orders Tab

Switch to the **🧾 Orders** tab.

**Talking points:**
- "You see the placed order with its DemoMart order number, total, and timestamp."
- "Expand the row to see individual order items — SKU, product title, quantity, price."
- "This mirrors what's in the DemoMart database. You could reconcile these records against vendor invoices."
- "The confirmation screenshot is stored but not displayed here — check the Run tab for that."

---

## Step 6: Storefront Tab

**Talking points:**
- "DemoMart is a mock e-commerce site — it has product pages, search, cart, checkout, and order history."
- "We built it to test the automation without touching a real vendor portal."
- "**The pitch:** Same automation, pointed at your vendor with a selector map + auth added."
- "To adapt this for a real vendor: change `MOCKSHOP_URL`, map your vendor's CSS selectors, add authentication (SSO/API key/basic auth), and the same pipeline works."
- "The origin guard ensures the browser never leaks to external domains — a safety net even in development."

---

## End-to-End Flow Summary

```
┌─────────────┐     ┌────────┐     ┌─────────────┐     ┌──────────┐     ┌──────────┐
│  Inventory   │ ──► │  Plan  │ ──► │  Browse     │ ──► │ Checkout │ ──► │  Record  │
│  (DB query)  │     │(Claude)│     │  Loop × N   │     │(Browser) │     │  (DB)    │
└─────────────┘     └────────┘     └──────┬──────┘     └──────────┘     └──────────┘
                                          │
                              ┌───────────┴────────────┐
                              │                        │
                          ┌───▼───┐             ┌──────▼──────┐
                          │Search │             │No match     │
                          │ +Match│             │ → Skip      │
                          │ +Cart │             │ → Continue  │
                          └───────┘             └─────────────┘
```

---

## Quick Reset

```bash
docker compose down -v      # Wipes DB, screenshots, everything
docker compose up --build   # Fresh start
```
