import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app import models  # noqa: F401
from app.api import issue_token, password_hash

ROLES = ["admin", "requester", "procurement", "receiving", "ap", "approver", "viewer"]
PASSWORD_HASHES = {role: password_hash(f"demo-{role}") for role in ROLES}


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(db_session):
    users = {}
    for role in ROLES:
        users[role] = models.UserAccount(username=role, role=role, password_hash=PASSWORD_HASHES[role])
        db_session.add(users[role])
    db_session.commit()
    def override_db():
        yield db_session
    app.dependency_overrides[get_db] = override_db
    test_client = TestClient(app)
    test_client.role_tokens = {role: issue_token(user) for role, user in users.items()}
    test_client.headers.update({"Authorization": f"Bearer {test_client.role_tokens['admin']}"})
    yield test_client
    test_client.close()
    app.dependency_overrides.clear()


@pytest.fixture
def base_records(db_session):
    supplier = models.Supplier(code="SUP-T01", name="Test Supplier", email="supplier@test.example", payment_terms_days=30)
    db_session.add(supplier)
    db_session.flush()
    req = models.Requisition(number="REQ-T01", requester="Tester", department="Finance", description="Test", status="APPROVED")
    db_session.add(req)
    db_session.flush()
    po = models.PurchaseOrder(number="PO-T01", supplier_id=supplier.id, requisition_id=req.id, status="OPEN")
    po.lines.append(models.PurchaseOrderLine(line_no=1, description="Test item", quantity_milli=10000, unit_price_paise=10000, tax_rate_bps=1800))
    db_session.add(po)
    db_session.flush()
    return supplier, req, po, po.lines[0]
