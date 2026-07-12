from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import os

from db import init_db, get_product, search_products, create_order, get_order, get_all_orders

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="demomart-secret-key-change-me")
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


@app.on_event("startup")
def startup():
    init_db()


def get_cart(request: Request):
    return request.session.get("cart", [])


def cart_count(request: Request):
    return sum(item["qty"] for item in get_cart(request))


@app.get("/")
def home(request: Request):
    from db import _get_conn, _row_to_dict
    conn = _get_conn()
    products = [_row_to_dict(r) for r in conn.execute("SELECT * FROM products ORDER BY id").fetchall()]
    conn.close()
    return templates.TemplateResponse("home.html", {
        "request": request, "products": products, "cart_count": cart_count(request),
    })


@app.get("/search")
def search(request: Request, q: str = ""):
    results = search_products(q) if q else []
    return templates.TemplateResponse("search.html", {
        "request": request, "query": q, "results": results, "cart_count": cart_count(request),
    })


@app.get("/product/{product_id}")
def product_detail(request: Request, product_id: int):
    product = get_product(product_id)
    if not product:
        return templates.TemplateResponse("home.html", {
            "request": request, "products": [], "cart_count": cart_count(request),
        }, status_code=404)
    return templates.TemplateResponse("product.html", {
        "request": request, "product": product, "cart_count": cart_count(request),
    })


@app.post("/cart/add")
def cart_add(request: Request, product_id: int = Form(...), title: str = Form(...), price: float = Form(...), qty: int = Form(1)):
    cart = get_cart(request)
    for item in cart:
        if item["product_id"] == product_id:
            item["qty"] += qty
            break
    else:
        cart.append({"product_id": product_id, "title": title, "price": price, "qty": qty})
    request.session["cart"] = cart
    return RedirectResponse(url="/cart", status_code=303)


@app.get("/cart")
def cart_page(request: Request):
    cart = get_cart(request)
    total = sum(item["price"] * item["qty"] for item in cart)
    return templates.TemplateResponse("cart.html", {
        "request": request, "cart": cart, "total": total, "cart_count": cart_count(request),
    })


@app.post("/cart/update")
def cart_update(request: Request, product_id: int = Form(...), qty: int = Form(0)):
    cart = get_cart(request)
    if qty <= 0:
        cart[:] = [item for item in cart if item["product_id"] != product_id]
    else:
        for item in cart:
            if item["product_id"] == product_id:
                item["qty"] = qty
                break
    request.session["cart"] = cart
    return RedirectResponse(url="/cart", status_code=303)


@app.get("/checkout")
def checkout_get(request: Request):
    cart = get_cart(request)
    if not cart:
        return RedirectResponse(url="/cart", status_code=303)
    total = sum(item["price"] * item["qty"] for item in cart)
    return templates.TemplateResponse("checkout.html", {
        "request": request, "cart": cart, "total": total, "cart_count": cart_count(request),
    })


@app.post("/checkout")
def checkout_post(request: Request, name: str = Form(...), email: str = Form(...), phone: str = Form(...), address: str = Form(...)):
    cart = get_cart(request)
    if not cart:
        return RedirectResponse(url="/cart", status_code=303)
    order_no = create_order([
        {"product_id": item["product_id"], "title": item["title"], "qty": item["qty"], "unit_price": item["price"]}
        for item in cart
    ])
    request.session["cart"] = []
    return RedirectResponse(url=f"/confirm/{order_no}", status_code=303)


@app.get("/confirm/{order_no}")
def confirm(request: Request, order_no: str):
    order = get_order(order_no)
    if not order:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("confirm.html", {
        "request": request, "order": order, "cart_count": cart_count(request),
    })


@app.get("/orders")
def orders_page(request: Request):
    orders = get_all_orders()
    return templates.TemplateResponse("orders.html", {
        "request": request, "orders": orders, "cart_count": cart_count(request),
    })
