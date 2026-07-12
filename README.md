# RPA Order Bot — AI Browser Automation Demo

An AI-powered browser automation agent that monitors inventory levels and autonomously places replenishment orders on a mock storefront (DemoMart).

## Architecture

- **Streamlit** frontend with 4 tabs: Inventory, Run Timeline, Orders, Storefront
- **Playwright** browser automates the DemoMart mock storefront
- **LangGraph** orchestrates: Plan → Browse Loop → Checkout → Record
- **Claude** (via `langchain-anthropic`) handles planning and product matching
- **PostgreSQL** stores inventory, run history, steps, and orders
- **FastAPI** mock storefront (DemoMart) with `data-testid` attributes for reliable automation

## Prerequisites

- Docker & Docker Compose
- Anthropic API key (Claude Sonnet 4)

## Quickstart

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

### 2. Build and run

```bash
docker compose up --build
```

This starts:
- **Streamlit app** at [http://localhost:8501](http://localhost:8501)
- **DemoMart** at [http://localhost:8090](http://localhost:8090)
- **PostgreSQL** database

### 3. Open the app

Navigate to [http://localhost:8501](http://localhost:8501).

The database seeds automatically on first load with 10 inventory items. Three are below their reorder threshold and will appear highlighted in red.

### 4. Run the reorder agent

Click **"Run Reorder Agent"** in the Inventory tab. Watch the Run tab for the live timeline.

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Claude API key (required) |
| `DATABASE_URL` | `postgresql+psycopg2://rpa:rpa_secret@db:5432/rpa_bot` | Postgres connection |
| `MOCKSHOP_URL` | `http://mockshop:8090` | DemoMart URL (change for real vendors) |
| `HEADED` | `false` | Run browser visibly (requires X/VNC) |
| `DATA_DIR` | `./data` | Screenshots and data storage |

## Headed Mode

To watch the browser automation visually:

```bash
HEADED=true docker compose up
```

Requires X11 forwarding on Linux or a VNC server in the container.

## Demo Script

See [DEMO_SCRIPT.md](DEMO_SCRIPT.md) for the full walkthrough.

## Reset

```bash
docker compose down -v    # Wipes database and screenshots
docker compose up --build # Fresh start
```

## Project Structure

```
app/
├── browser.py          # Playwright context/screenshot management
├── db.py               # SQLAlchemy models and DB functions
├── llm.py              # Claude LLM wrapper
├── settings.py         # Environment configuration
├── main.py             # Streamlit entry point
├── scripted_run.py     # Phase 1 deterministic single-item run
├── steps/              # Browser automation step functions
│   ├── search.py       # Search DemoMart for a product
│   ├── match.py        # Claude-based product matching
│   ├── cart.py         # Add to cart
│   └── checkout.py     # Checkout and order confirmation
├── graph/              # LangGraph orchestration
│   ├── state.py        # Typed state definition
│   ├── registry.py     # Page/context registry
│   ├── build.py        # Graph construction and compilation
│   └── nodes/          # Graph node functions
│       ├── plan.py     # Shopping plan generation
│       ├── browse.py   # Per-item browse/match/cart loop
│       ├── checkout_node.py
│       └── record.py   # Database recording
├── tabs/               # Streamlit tab components
│   ├── inventory.py    # Inventory management with data editor
│   ├── run.py          # Run timeline with screenshots
│   ├── orders.py       # Placed orders listing
│   └── storefront.py   # DemoMart info and links
└── tests/              # Unit tests
```
