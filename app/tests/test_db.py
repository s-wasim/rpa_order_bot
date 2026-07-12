import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone

from app.db import Base, Inventory, Run, RunStep, Order, OrderItem, seed_inventory


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def test_init_db(db_session):
    assert Inventory.__tablename__ == "inventory"
    assert Run.__tablename__ == "runs"
    assert RunStep.__tablename__ == "run_steps"
    assert Order.__tablename__ == "orders"
    assert OrderItem.__tablename__ == "order_items"


def test_seed_inventory(db_session):
    seed_inventory(db_session)
    count = db_session.query(Inventory).count()
    assert count == 10

    db_session.rollback()
    seed_inventory(db_session)
    count2 = db_session.query(Inventory).count()
    assert count2 == 10

    low_stock = (
        db_session.query(Inventory)
        .filter(Inventory.qty + Inventory.on_order < Inventory.reorder_threshold)
        .count()
    )
    assert low_stock == 3


def test_crud_run(db_session):
    run = Run(status="running")
    db_session.add(run)
    db_session.flush()

    step1 = RunStep(run_id=run.id, seq=1, label="Navigate", status="running")
    step2 = RunStep(run_id=run.id, seq=2, label="Order", status="running")
    db_session.add_all([step1, step2])
    db_session.flush()

    db_session.commit()

    fetched = db_session.query(Run).filter_by(id=run.id).one()
    assert fetched.status == "running"
    assert len(fetched.steps) == 2
    assert fetched.steps[0].label == "Navigate"


def test_crud_order(db_session):
    inv = Inventory(
        sku="TEST-SKU-001",
        name="Test Item",
        qty=10,
        reorder_threshold=3,
        reorder_qty=5,
        on_order=0,
    )
    db_session.add(inv)
    db_session.flush()

    run = Run(status="running")
    db_session.add(run)
    db_session.flush()

    order = Order(run_id=run.id, demomart_order_no="DM-001", total=29.99)
    db_session.add(order)
    db_session.flush()

    item = OrderItem(
        order_id=order.id,
        sku="TEST-SKU-001",
        product_title="Test Item",
        qty=2,
        unit_price=14.995,
    )
    db_session.add(item)
    db_session.commit()

    fetched = db_session.query(Order).filter_by(id=order.id).one()
    assert fetched.demomart_order_no == "DM-001"
    assert fetched.total == 29.99
    assert len(fetched.items) == 1
    assert fetched.items[0].qty == 2


def test_cascade_delete(db_session):
    run = Run(status="running")
    db_session.add(run)
    db_session.flush()

    step = RunStep(run_id=run.id, seq=1, label="Step 1", status="running")
    db_session.add(step)
    db_session.flush()

    run_id = run.id
    step_id = step.id
    db_session.delete(run)
    db_session.commit()

    assert db_session.query(Run).filter_by(id=run_id).count() == 0
    assert db_session.query(RunStep).filter_by(id=step_id).count() == 0
