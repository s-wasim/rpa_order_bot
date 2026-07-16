import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.api.inventory import router as inventory_router
from app.api.orders import router as orders_router
from app.api.runs import router as runs_router
from app.api.screenshots import router as screenshots_router
from app.api.storefront import router as storefront_router
from app.db import init_db, get_session, seed_inventory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
INDEX_FILE = FRONTEND_DIR / "RPA Order Bot.dc.html"

app = FastAPI(title="RPA Order Bot")


@app.on_event("startup")
def _startup() -> None:
    init_db()
    with get_session() as session:
        seed_inventory(session)


# API routers (registered before the catch-all static mount so they take
# precedence over file serving).
app.include_router(health_router)
app.include_router(inventory_router)
app.include_router(orders_router)
app.include_router(runs_router)
app.include_router(screenshots_router)
app.include_router(storefront_router)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(INDEX_FILE)


# Serve the dc-runtime frontend (support.js, adapter.js, uploads/*) from the
# same origin as the API.
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
