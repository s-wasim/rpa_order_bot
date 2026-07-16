from sqlalchemy import text
import httpx
from fastapi import APIRouter

from app.api.schemas import HealthOut
from app.db import get_session
from app import settings

router = APIRouter()


@router.get("/api/health", response_model=HealthOut)
def get_health():
    db_ok = True
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    demomart_ok = True
    try:
        resp = httpx.get(settings.MOCKSHOP_URL, timeout=3.0)
        demomart_ok = resp.status_code < 500
    except Exception:
        demomart_ok = False

    error = None if demomart_ok else "DemoMart storefront is unreachable"
    return HealthOut(db_ok=db_ok, demomart_ok=demomart_ok, error=error)
