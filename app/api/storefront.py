import httpx
from fastapi import APIRouter

from app.api.schemas import StorefrontInfoOut, StorefrontPreviewOut, StorefrontProductOut
from app import settings

router = APIRouter()


@router.get("/api/storefront", response_model=StorefrontInfoOut)
def get_storefront_info():
    url = settings.MOCKSHOP_URL.replace("mockshop", "localhost")
    return StorefrontInfoOut(url=url)


@router.get("/api/storefront/preview", response_model=StorefrontPreviewOut)
def get_storefront_preview():
    try:
        resp = httpx.get(f"{settings.MOCKSHOP_URL}/api/products", timeout=5.0)
        resp.raise_for_status()
        products = resp.json()
    except Exception:
        return StorefrontPreviewOut(products=[], total_count=0)

    preview = [
        StorefrontProductOut(
            title=p["title"], price=p["price"],
            stock_badge="In stock" if p["stock"] else "Out of stock",
        )
        for p in products[:6]
    ]
    return StorefrontPreviewOut(products=preview, total_count=len(products))
