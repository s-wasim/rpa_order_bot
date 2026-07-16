from fastapi import APIRouter

from app.api.schemas import OrderOut, OrderItemOut
from app.db import get_session, Order

router = APIRouter()


@router.get("/api/orders", response_model=list[OrderOut])
def list_orders():
    with get_session() as session:
        orders = session.query(Order).order_by(Order.created_at.desc()).all()
        return [
            OrderOut(
                demomart_order_no=o.demomart_order_no, total=o.total,
                created_at=o.created_at, run_id=o.run_id,
                items=[
                    OrderItemOut(sku=i.sku, product_title=i.product_title, qty=i.qty, unit_price=i.unit_price)
                    for i in o.items
                ],
            )
            for o in orders
        ]
