# RPA Order Bot: Streamlit → FastAPI + dc-runtime frontend migration

## Context

`rpa_order_bot` currently ships a Streamlit UI (`app/main.py` + `app/tabs/*.py`) over a LangGraph-driven browser-automation backend (Playwright + Claude structured output, against the `mockshop` demo storefront). A new dc-runtime frontend template already exists at `frontend/RPA Order Bot.dc.html` (+ `adapter.js`, `support.js`), built in mock mode (`API_BASE = null` in `adapter.js`) with every function documented against an intended real endpoint. This mirrors migrations already completed for `ai_knowledge_bot` and `inbound_lead_responder`.

Goal: replace the Streamlit UI entirely with this frontend, backed by a real FastAPI service, with no functional gaps versus the current Streamlit app (plus two small feature completions the mock UI stubs out: a real storefront product preview, and real screenshot rendering).

## Architecture

Single FastAPI app (`app/server.py`), following the exact pattern used in the two sibling migrations: API routers registered first, then the `frontend/` directory mounted as static files serving the same origin/port. `docker-compose.yml`'s `app` service Dockerfile CMD switches from `streamlit run ...` to `uvicorn app.server:app --host 0.0.0.0 --port 8501`. `app/requirements.txt` drops `streamlit`, adds `fastapi`, `uvicorn`, `httpx`. All Streamlit-only files (`app/main.py`, `app/tabs/*.py`) are deleted once equivalent routes exist and are verified. `app/scripted_run.py` (dead "Phase 1" code, unreferenced by the current UI) is left untouched — out of scope for this migration.

## API endpoints (`app/api/`, new package: `schemas.py`, `health.py`, `inventory.py`, `runs.py`, `orders.py`, `storefront.py`)

| Endpoint | Behavior |
|---|---|
| `GET /api/health` | `{db_ok, demomart_ok, error?}` — DB ping + HTTP check against `MOCKSHOP_URL` |
| `GET /api/inventory` | Wraps the query in `app/tabs/inventory.py:10-24` |
| `POST /api/inventory/thresholds` | Wraps the update loop in `app/tabs/inventory.py:60-65` |
| `POST /api/runs` | Creates `Run(status="running")` **only if no other run has `status="running"`**; else returns `{ok:false, reason:"..."}` (exact shape the frontend already expects). On success, launches `run_agent(run_id)` on a daemon `threading.Thread` and returns `{ok:true, run_id}` immediately — same one-browser-at-a-time model as today, no longer blocking the request. |
| `GET /api/runs` | Wraps `app/tabs/run.py:13` (`order_by(created_at.desc()).limit(20)`) |
| `GET /api/runs/{id}` | Wraps `app/tabs/run.py:27-34`, shaped as `{plan_json, summary_json, status, steps}` |
| `GET /api/runs/{id}/stream` | SSE. Polls `Run`/`RunStep` rows for that `run_id` every ~500ms, emitting `plan`/`step`/`summary`/`status` frames for new/changed data, until status is terminal. `getRun()` already hydrates full history on load, so only forward-going events need to stream. |
| `GET /api/orders` | Wraps `app/tabs/orders.py:9-29` |
| `GET /api/screenshots/{run_id}/{filename}` | `FileResponse` from `DATA_DIR/screenshots/{run_id}/{filename}`, filename validated against path traversal (reject `..`, `/`, `\`) |
| `GET /api/storefront` | Wraps `app/tabs/storefront.py:8` |

Run-stream design note: sibling projects use a callback+`queue.Queue` pattern for true push-based SSE (`ai_knowledge_bot/app/api/ingest.py`). That requires threading a `progress_callback` through the already-tested LangGraph nodes. DB-polling gives the identical frontend contract with zero changes to graph internals; ~500ms latency is imperceptible against multi-second Playwright steps. Chosen for lower risk.

## Storefront preview (mockshop addition)

Add `GET /api/products` to `mockshop/main.py`, returning all catalog rows (`id, title, price, stock, image_url`) from the existing SQLite `products` table. The RPA bot's `GET /api/storefront/preview` calls this over HTTP via `httpx` (using `MOCKSHOP_URL`), selects 6 products, maps `stock` (bool) → `stock_badge` (`"In stock"` / `"Out of stock"` — mockshop has no 3-tier "low stock" concept, so the mock UI's "Low stock" badge value has no real equivalent and won't appear in production data), and returns `{products, total_count: <actual catalog count>}`.

## Frontend template edits

- `adapter.js`: set real `API_BASE`, replace every mock function body with a real `fetch`/`EventSource` call per the endpoint table above. Remove `__debugToggleDemomart()` and its Ctrl+Shift+H binding in the component (dev-only mock affordance, no backend meaning).
- `RPA Order Bot.dc.html`: replace the two screenshot placeholder blocks (timeline thumbnail ~line 270-275, lightbox ~line 446) with real `<img src="/api/screenshots/{run_id}/{filename}">` tags inside the existing fake-browser-chrome frame, falling back to the camera-icon placeholder on image load error.

## Testing

New `app/tests/test_api_*.py` (one per router), using an in-memory SQLite DB + FastAPI `TestClient`, following the pattern already established in the sibling projects. Explicit coverage for: run-concurrency rejection (`POST /api/runs` while one is active), screenshot path-traversal guard, and the storefront-preview → mockshop HTTP call (mocked).

## Out of scope

- `app/scripted_run.py` — left as dead code, not ported or removed.
- Any change to `mockshop`'s existing HTML-rendering routes — only the new `GET /api/products` JSON endpoint is added.
