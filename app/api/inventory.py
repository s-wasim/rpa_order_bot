from fastapi import APIRouter

from app.api.schemas import InventoryItemOut, ThresholdEdit
from app.db import get_session, Inventory

router = APIRouter()


def _is_low(item: Inventory) -> bool:
    return (item.qty + item.on_order) < item.reorder_threshold


@router.get("/api/inventory", response_model=list[InventoryItemOut])
def get_inventory():
    with get_session() as session:
        items = session.query(Inventory).order_by(Inventory.sku).all()
        return [
            InventoryItemOut(
                sku=i.sku, name=i.name, qty=i.qty,
                reorder_threshold=i.reorder_threshold, reorder_qty=i.reorder_qty,
                on_order=i.on_order, low=_is_low(i),
            )
            for i in items
        ]


@router.post("/api/inventory/thresholds")
def save_thresholds(edits: list[ThresholdEdit]):
    with get_session() as session:
        for edit in edits:
            inv = session.query(Inventory).filter(Inventory.sku == edit.sku).first()
            if inv:
                inv.reorder_threshold = edit.reorder_threshold
                inv.reorder_qty = edit.reorder_qty
    return {"ok": True}
