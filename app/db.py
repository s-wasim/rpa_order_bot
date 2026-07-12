import json
import time
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime, timezone

from . import settings

Base = declarative_base()


class Inventory(Base):
    __tablename__ = "inventory"

    sku = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    qty = Column(Integer, nullable=False, default=0)
    reorder_threshold = Column(Integer, nullable=False, default=0)
    reorder_qty = Column(Integer, nullable=False, default=0)
    on_order = Column(Integer, nullable=False, default=0)


class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    status = Column(String, nullable=False, default="running")
    plan_json = Column(JSON, nullable=True)
    summary_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    steps = relationship("RunStep", back_populates="run", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="run")


class RunStep(Base):
    __tablename__ = "run_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    seq = Column(Integer, nullable=False)
    label = Column(String, nullable=False)
    detail = Column(Text, nullable=True)
    screenshot_path = Column(String, nullable=True)
    status = Column(String, nullable=False, default="running")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    run = relationship("Run", back_populates="steps")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False)
    demomart_order_no = Column(String, nullable=False)
    total = Column(Float, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    run = relationship("Run", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    sku = Column(String, ForeignKey("inventory.sku"), nullable=True)
    product_title = Column(String, nullable=False)
    qty = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)

    order = relationship("Order", back_populates="items")


engine = None
SessionLocal = None


def init_db(retries=5, delay=5):
    global engine, SessionLocal
    url = settings.DATABASE_URL
    for attempt in range(1, retries + 1):
        try:
            engine = create_engine(url, pool_pre_ping=True)
            Base.metadata.create_all(engine)
            SessionLocal = sessionmaker(bind=engine)
            return
        except Exception as e:
            if attempt < retries:
                time.sleep(delay)
            else:
                raise e


@contextmanager
def get_session():
    if SessionLocal is None:
        init_db()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def seed_inventory(session):
    if session.query(Inventory).count() > 0:
        return

    items = [
        Inventory(sku="THERMAL-PASTE-001", name="Thermal Paste 4g Tube", qty=2, reorder_threshold=5, reorder_qty=10, on_order=0),
        Inventory(sku="USB-C-HUB-002", name="USB-C Multiport Hub", qty=8, reorder_threshold=5, reorder_qty=5, on_order=0),
        Inventory(sku="MECH-KEYB-003", name="Mechanical Keyboard", qty=1, reorder_threshold=3, reorder_qty=3, on_order=0),
        Inventory(sku="HDMI-CABLE-004", name="HDMI 2.1 Cable 3m", qty=15, reorder_threshold=10, reorder_qty=20, on_order=0),
        Inventory(sku="MOUSE-PAD-005", name="Large Mouse Pad", qty=8, reorder_threshold=5, reorder_qty=10, on_order=0),
        Inventory(sku="SSD-1TB-006", name="SSD 1TB Internal", qty=6, reorder_threshold=3, reorder_qty=5, on_order=0),
        Inventory(sku="WEBCAM-007", name="1080p Webcam", qty=10, reorder_threshold=4, reorder_qty=5, on_order=0),
        Inventory(sku="NO-MATCH-008", name="Proprietary Connector Kit", qty=1, reorder_threshold=3, reorder_qty=3, on_order=0),
        Inventory(sku="WIRELESS-MOUSE-009", name="Wireless Mouse", qty=8, reorder_threshold=5, reorder_qty=8, on_order=0),
        Inventory(sku="USB-MICRO-010", name="USB Microphone", qty=6, reorder_threshold=3, reorder_qty=4, on_order=0),
    ]
    for item in items:
        session.add(item)
    session.flush()
