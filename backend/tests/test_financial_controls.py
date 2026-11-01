from datetime import date, timedelta
from decimal import Decimal

import pytest

from app import models
from app.schemas import LineInput
from app.services import extended_paise, match_invoice, quantity_milli, refresh_invoice_match, store_invoice_lines, tax_paise


def auth(client, role):
    return {"Authorization": f"Bearer {client.role_tokens[role]}"}


@pytest.mark.parametrize("qty,expected", [("0.001", 1), ("1", 1000), ("1.250", 1250), ("99.999", 99999)])
def test_quantity_precision(qty, expected):
    assert quantity_milli(Decimal(qty)) == expected


@pytest.mark.parametrize("qty", ["0.0001", "1.0001", "5.1239"])
def test_quantity_rejects_precision_beyond_milli(qty):
    with pytest.raises(ValueError):
        quantity_milli(Decimal(qty))


@pytest.mark.parametrize("unit,qty,expected", [(100, "1", 100), (100, "1.5", 150), (1, "0.5", 1), (3, "0.5", 2)])
def test_line_extension_rounds_half_up(unit, qty, expected):
    assert extended_paise(unit, Decimal(qty)) == expected


@pytest.mark.parametrize("subtotal,bps,expected", [(10000, 1800, 1800), (1, 5000, 1), (3, 5000, 2), (10000, 0, 0)])
def test_tax_is_line_level_rounded(subtotal, bps, expected):
    assert tax_paise(subtotal, bps) == expected


def test_supplier_registration_and_duplicate_rejected(client):
    data = {"code": "SUP-X", "name": "Supplier X", "email": "x@sample.example"}
    assert client.post("/api/suppliers", json=data, headers=auth(client, "procurement")).status_code == 201
    assert client.post("/api/suppliers", json=data, headers=auth(client, "procurement")).status_code == 409


def test_login_returns_expiring_bearer_session(client):
    response = client.post("/api/auth/login", json={"username": "ap", "password": "demo-ap"})
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer" and response.json()["expires_in"] == 28800


def test_invalid_password_rejected(client):
    assert client.post("/api/auth/login", json={"username": "ap", "password": "incorrect"}).status_code == 401


def test_database_rejects_duplicate_invoice_number(db_session, base_records):
    supplier = base_records[0]
    db_session.add(models.Invoice(number="INV-UNIQUE", supplier_id=supplier.id, invoice_date=date.today(), due_date=date.today()))
    db_session.flush()
    db_session.add(models.Invoice(number="INV-UNIQUE", supplier_id=supplier.id, invoice_date=date.today(), due_date=date.today()))
    with pytest.raises(Exception):
        db_session.flush()


def test_supplier_validation_rejects_bad_email(client):
    assert client.post("/api/suppliers", json={"code": "SUP-X", "name": "Supplier X", "email": "bad"}, headers=auth(client, "procurement")).status_code == 422


def test_supplier_deactivation(client, base_records):
    supplier = base_records[0]
    response = client.patch(f"/api/suppliers/{supplier.id}", json={"active": False}, headers=auth(client, "procurement"))
    assert response.status_code == 200 and response.json()["active"] is False


def test_requisition_submission_and_approval(client, base_records):
    response = client.post("/api/requisitions", json={"requester": "Asha Rao", "department": "IT", "description": "Laptop accessories", "lines": [{"description": "Dock", "quantity": "2", "unit_price_paise": 50000}]}, headers=auth(client, "requester"))
    assert response.status_code == 201
    req_id = response.json()["id"]
    approved = client.post(f"/api/requisitions/{req_id}/decision", json={"actor": "Manager", "decision": "APPROVED"}, headers=auth(client, "approver"))
    assert approved.json()["status"] == "APPROVED"


def test_requisition_transition_cannot_repeat(client, base_records):
    req = base_records[1]
    assert client.post(f"/api/requisitions/{req.id}/decision", json={"actor": "Manager", "decision": "APPROVED"}, headers=auth(client, "approver")).status_code == 409


def test_approval_identity_comes_from_authenticated_account(client):
    created = client.post("/api/requisitions", json={"requester": "Test User", "department": "Finance", "description": "Approve this", "lines": [{"description": "Item", "quantity": "1", "unit_price_paise": 100}]}, headers=auth(client, "requester"))
    req_id = created.json()["id"]
    approved = client.post(f"/api/requisitions/{req_id}/decision", json={"actor": "Forged Name", "decision": "APPROVED"}, headers=auth(client, "approver"))
    assert approved.status_code == 200
    from app.core.database import get_db
    session = client.app.dependency_overrides[get_db]().__next__()
    approval = session.query(models.Approval).filter_by(entity_type="REQUISITION", entity_id=req_id).one()
    event = session.query(models.AuditEvent).filter_by(entity_type="requisition", entity_id=req_id, action="APPROVED").one()
    assert approval.approver == "approver" and event.actor == "approver"


def test_po_requires_active_supplier(client):
    assert client.post("/api/purchase-orders", json={"supplier_id": 999, "lines": [{"description": "Thing", "quantity": "1", "unit_price_paise": 100}]}, headers=auth(client, "procurement")).status_code == 422


def test_po_cannot_reference_unapproved_requisition(client, base_records):
    supplier = base_records[0]
    req = models.Requisition(number="REQ-DRAFT", requester="T", department="IT", description="test", status="SUBMITTED")
    # Create through API to keep the test on a real request path.
    req_response = client.post("/api/requisitions", json={"requester": "Test Requester", "department": "IT", "description": "test", "lines": [{"description": "Thing", "quantity": "1", "unit_price_paise": 100}]}, headers=auth(client, "requester"))
    req_id = req_response.json()["id"]
    po = client.post("/api/purchase-orders", json={"supplier_id": supplier.id, "requisition_id": req_id, "lines": [{"description": "Thing", "quantity": "1", "unit_price_paise": 100}]}, headers=auth(client, "procurement"))
    assert po.status_code == 409


def test_receipt_validates_selected_po_line(client, base_records):
    po = base_records[2]
    body = {"purchase_order_id": po.id, "received_by": "Receiver", "lines": [{"purchase_order_line_id": 999, "received_quantity": "1", "accepted_quantity": "1"}]}
    assert client.post("/api/goods-receipts", json=body, headers=auth(client, "receiving")).status_code == 422


def test_receipt_accepted_cannot_exceed_received(client, base_records):
    line = base_records[3]
    body = {"purchase_order_id": line.purchase_order_id, "received_by": "Receiver", "lines": [{"purchase_order_line_id": line.id, "received_quantity": "1", "accepted_quantity": "2"}]}
    assert client.post("/api/goods-receipts", json=body, headers=auth(client, "receiving")).status_code == 422


def test_cumulative_receipt_cannot_exceed_order(client, base_records):
    po, line = base_records[2], base_records[3]
    def receive(qty):
        return client.post("/api/goods-receipts", json={"purchase_order_id": po.id, "received_by": "Receiver", "lines": [{"purchase_order_line_id": line.id, "received_quantity": str(qty), "accepted_quantity": str(qty)}]}, headers=auth(client, "receiving"))
    assert receive(8).status_code == 201
    assert receive(3).status_code == 409


def test_duplicate_lines_in_one_receipt_cannot_overreceive(client, base_records):
    po, line = base_records[2], base_records[3]
    body = {"purchase_order_id": po.id, "received_by": "Receiver", "lines": [
        {"purchase_order_line_id": line.id, "received_quantity": "6", "accepted_quantity": "6"},
        {"purchase_order_line_id": line.id, "received_quantity": "6", "accepted_quantity": "6"},
    ]}
    assert client.post("/api/goods-receipts", json=body, headers=auth(client, "receiving")).status_code == 409


def test_duplicate_invoice_number_rejected(client, base_records):
    supplier = base_records[0]
    body = {"number": "DUP-1", "supplier_id": supplier.id, "invoice_date": str(date.today()), "due_date": str(date.today()), "lines": [{"description": "service", "quantity": "1", "unit_price_paise": 100}]}
    assert client.post("/api/invoices", json=body, headers=auth(client, "ap")).status_code == 201
    assert client.post("/api/invoices", json=body, headers=auth(client, "ap")).status_code == 409


def test_invoice_due_date_validation(client, base_records):
    supplier = base_records[0]
    body = {"number": "INV-DATE", "supplier_id": supplier.id, "invoice_date": str(date.today()), "due_date": str(date.today()-timedelta(days=1)), "lines": [{"description": "service", "quantity": "1", "unit_price_paise": 100}]}
    assert client.post("/api/invoices", json=body, headers=auth(client, "ap")).status_code == 422


def test_invoice_supplier_must_match_po(client, base_records):
    supplier, _, po, line = base_records
    other = models.Supplier(code="SUP-T02", name="Other", email="other@test.example")
    client.post("/api/suppliers", json={"code": other.code, "name": other.name, "email": other.email}, headers=auth(client, "procurement"))
    other_id = next(x["id"] for x in client.get("/api/suppliers").json() if x["code"] == "SUP-T02")
    body = {"number": "INV-PO", "supplier_id": other_id, "purchase_order_id": po.id, "invoice_date": str(date.today()), "due_date": str(date.today()), "lines": [{"description": "item", "quantity": "1", "unit_price_paise": line.unit_price_paise, "purchase_order_line_id": line.id}]}
    assert client.post("/api/invoices", json=body, headers=auth(client, "ap")).status_code == 422


def test_missing_receipt_is_exception(db_session, base_records):
    supplier, _, po, line = base_records
    invoice = models.Invoice(number="INV-NORC", supplier_id=supplier.id, purchase_order_id=po.id, invoice_date=date.today(), due_date=date.today())
    store_invoice_lines(invoice, [LineInput(description="Test item", quantity=Decimal("1"), unit_price_paise=line.unit_price_paise, purchase_order_line_id=line.id)])
    db_session.add(invoice); db_session.flush()
    findings = match_invoice(db_session, invoice)
    assert "MISSING_RECEIPT" in {x[0] for x in findings}


def test_price_mismatch_is_exception(db_session, base_records):
    supplier, _, po, line = base_records
    receipt = models.GoodsReceipt(number="GRN-T01", purchase_order_id=po.id, received_by="Receiver")
    receipt.lines.append(models.GoodsReceiptLine(purchase_order_line_id=line.id, received_quantity_milli=10000, accepted_quantity_milli=10000, rejected_quantity_milli=0))
    db_session.add(receipt); db_session.flush()
    invoice = models.Invoice(number="INV-PRICE", supplier_id=supplier.id, purchase_order_id=po.id, invoice_date=date.today(), due_date=date.today())
    store_invoice_lines(invoice, [LineInput(description="Test item", quantity=Decimal("1"), unit_price_paise=line.unit_price_paise+1, purchase_order_line_id=line.id)])
    db_session.add(invoice); db_session.flush()
    assert "PRICE_VARIANCE" in {x[0] for x in match_invoice(db_session, invoice)}


def test_cumulative_invoice_quantity_detected(db_session, base_records):
    supplier, _, po, line = base_records
    first = models.Invoice(number="INV-C1", supplier_id=supplier.id, purchase_order_id=po.id, invoice_date=date.today(), due_date=date.today())
    store_invoice_lines(first, [LineInput(description="Test", quantity=Decimal("6"), unit_price_paise=line.unit_price_paise, purchase_order_line_id=line.id)])
    db_session.add(first); db_session.flush()
    second = models.Invoice(number="INV-C2", supplier_id=supplier.id, purchase_order_id=po.id, invoice_date=date.today(), due_date=date.today())
    store_invoice_lines(second, [LineInput(description="Test", quantity=Decimal("5"), unit_price_paise=line.unit_price_paise, purchase_order_line_id=line.id)])
    db_session.add(second); db_session.flush()
    assert "PO_QUANTITY_VARIANCE" in {x[0] for x in match_invoice(db_session, second)}


def test_duplicate_lines_in_one_invoice_count_toward_accepted_quantity(db_session, base_records):
    supplier, _, po, line = base_records
    line.quantity_milli = 20000
    receipt = models.GoodsReceipt(number="GRN-DUPLINE", purchase_order_id=po.id, received_by="Receiver")
    receipt.lines.append(models.GoodsReceiptLine(purchase_order_line_id=line.id, received_quantity_milli=10000, accepted_quantity_milli=10000, rejected_quantity_milli=0))
    db_session.add(receipt); db_session.flush()
    invoice = models.Invoice(number="INV-DUPLINE", supplier_id=supplier.id, purchase_order_id=po.id, invoice_date=date.today(), due_date=date.today())
    split_line = LineInput(description="Split line", quantity=Decimal("6"), unit_price_paise=line.unit_price_paise, purchase_order_line_id=line.id)
    store_invoice_lines(invoice, [split_line, split_line])
    db_session.add(invoice); db_session.flush()
    assert "RECEIPT_QUANTITY_VARIANCE" in {x[0] for x in match_invoice(db_session, invoice)}


def test_tax_discrepancy_detected(db_session, base_records):
    supplier, _, po, line = base_records
    receipt = models.GoodsReceipt(number="GRN-TAX", purchase_order_id=po.id, received_by="Receiver")
    receipt.lines.append(models.GoodsReceiptLine(purchase_order_line_id=line.id, received_quantity_milli=1000, accepted_quantity_milli=1000, rejected_quantity_milli=0))
    db_session.add(receipt); db_session.flush()
    invoice = models.Invoice(number="INV-TAX", supplier_id=supplier.id, purchase_order_id=po.id, invoice_date=date.today(), due_date=date.today())
    store_invoice_lines(invoice, [LineInput(description="Test", quantity=Decimal("1"), unit_price_paise=line.unit_price_paise, purchase_order_line_id=line.id)])
    invoice.tax_paise += 1
    db_session.add(invoice); db_session.flush()
    assert "TAX_VARIANCE" in {x[0] for x in match_invoice(db_session, invoice)}


def test_approval_permission_denied_for_viewer(client, base_records):
    req = base_records[1]
    response = client.post(f"/api/requisitions/{req.id}/decision", json={"actor": "Viewer", "decision": "APPROVED"}, headers=auth(client, "viewer"))
    assert response.status_code == 403


def test_unmatched_invoice_cannot_be_approved(client, base_records):
    supplier = base_records[0]
    created = client.post("/api/invoices", json={"number": "INV-UNMATCHED", "supplier_id": supplier.id, "invoice_date": str(date.today()), "due_date": str(date.today()), "lines": [{"description": "service", "quantity": "1", "unit_price_paise": 100}]}, headers=auth(client, "ap")).json()
    response = client.post(f"/api/invoices/{created['id']}/decision", json={"actor": "Approver", "decision": "APPROVED"}, headers=auth(client, "approver"))
    assert response.status_code == 409


def test_partial_and_full_payments(client, base_records):
    supplier = base_records[0]
    inv = models.Invoice(number="INV-PAY", supplier_id=supplier.id, invoice_date=date.today(), due_date=date.today(), status="APPROVED", match_outcome="APPROVED", total_paise=1000)
    # Persist the approved test invoice through the overridden real test session.
    from app.core.database import get_db
    session = client.app.dependency_overrides[get_db]().__next__()
    session.add(inv); session.commit()
    first = client.post("/api/payments", json={"invoice_id": inv.id, "amount_paise": 400}, headers=auth(client, "ap"))
    assert first.status_code == 201 and first.json()["invoice"]["status"] == "PARTIALLY_PAID"
    second = client.post("/api/payments", json={"invoice_id": inv.id, "amount_paise": 600}, headers=auth(client, "ap"))
    assert second.status_code == 201 and second.json()["invoice"]["status"] == "PAID"


def test_overpayment_prevented(client, base_records):
    supplier = base_records[0]
    inv = models.Invoice(number="INV-OVER", supplier_id=supplier.id, invoice_date=date.today(), due_date=date.today(), status="APPROVED", match_outcome="APPROVED", total_paise=100)
    from app.core.database import get_db
    session = client.app.dependency_overrides[get_db]().__next__()
    session.add(inv); session.commit()
    response = client.post("/api/payments", json={"invoice_id": inv.id, "amount_paise": 101}, headers=auth(client, "ap"))
    assert response.status_code == 409
    assert client.get("/api/payments").json() == []


def test_two_way_match_does_not_require_receipt(db_session, base_records):
    supplier, _, po, line = base_records
    invoice = models.Invoice(number="INV-2WAY", supplier_id=supplier.id, purchase_order_id=po.id, matching_mode="TWO_WAY", invoice_date=date.today(), due_date=date.today())
    store_invoice_lines(invoice, [LineInput(description="Test", quantity=Decimal("1"), unit_price_paise=line.unit_price_paise, purchase_order_line_id=line.id)])
    db_session.add(invoice); db_session.flush()
    assert match_invoice(db_session, invoice) == []


def test_three_way_match_requires_receipt(db_session, base_records):
    supplier, _, po, line = base_records
    invoice = models.Invoice(number="INV-3WAY", supplier_id=supplier.id, purchase_order_id=po.id, matching_mode="THREE_WAY", invoice_date=date.today(), due_date=date.today())
    store_invoice_lines(invoice, [LineInput(description="Test", quantity=Decimal("1"), unit_price_paise=line.unit_price_paise, purchase_order_line_id=line.id)])
    db_session.add(invoice); db_session.flush()
    assert "MISSING_RECEIPT" in {x[0] for x in match_invoice(db_session, invoice)}


def test_clean_three_way_match_uses_accepted_quantity(db_session, base_records):
    supplier, _, po, line = base_records
    receipt = models.GoodsReceipt(number="GRN-OK", purchase_order_id=po.id, received_by="Receiver")
    receipt.lines.append(models.GoodsReceiptLine(purchase_order_line_id=line.id, received_quantity_milli=2000, accepted_quantity_milli=2000, rejected_quantity_milli=0))
    db_session.add(receipt); db_session.flush()
    invoice = models.Invoice(number="INV-OK", supplier_id=supplier.id, purchase_order_id=po.id, invoice_date=date.today(), due_date=date.today())
    store_invoice_lines(invoice, [LineInput(description="Test", quantity=Decimal("2"), unit_price_paise=line.unit_price_paise, purchase_order_line_id=line.id)])
    db_session.add(invoice); db_session.flush()
    assert match_invoice(db_session, invoice) == []


def test_correction_clears_stale_exception_and_preserves_history(db_session, base_records):
    supplier, _, po, line = base_records
    inv = models.Invoice(number="INV-CORR", supplier_id=supplier.id, purchase_order_id=po.id, invoice_date=date.today(), due_date=date.today())
    store_invoice_lines(inv, [LineInput(description="Test", quantity=Decimal("1"), unit_price_paise=line.unit_price_paise+10, purchase_order_line_id=line.id)])
    db_session.add(inv); db_session.flush()
    refresh_invoice_match(db_session, inv); db_session.flush()
    exception = db_session.query(models.ExceptionRecord).filter_by(invoice_id=inv.id, category="PRICE_VARIANCE").one()
    assert exception.status == "OPEN"
    inv.lines.clear(); db_session.flush()
    store_invoice_lines(inv, [LineInput(description="Test", quantity=Decimal("1"), unit_price_paise=line.unit_price_paise, purchase_order_line_id=line.id)])
    refresh_invoice_match(db_session, inv); db_session.flush()
    assert exception.status == "RESOLVED"


def test_csv_import_reports_duplicate_rows_and_imports_valid(client, base_records):
    import io
    content = "code,name,email,payment_terms_days\nSUP-CSV,CSV Supplier,csv@example.com,30\nSUP-CSV,Duplicate,dupe@example.com,30\n,Missing,missing@example.com,30\n"
    response = client.post("/api/suppliers/import.csv", files={"file": ("suppliers.csv", io.BytesIO(content.encode()), "text/csv")}, headers=auth(client, "procurement"))
    assert response.status_code == 200
    assert response.json()["created_count"] == 1 and len(response.json()["errors"]) == 2


def test_csv_export_has_supplier_header(client, base_records):
    response = client.get("/api/export/suppliers.csv")
    assert response.status_code == 200 and response.text.startswith("code,name,contact_person")


def test_viewer_cannot_record_payment(client, base_records):
    response = client.post("/api/payments", json={"invoice_id": 1, "amount_paise": 1}, headers=auth(client, "viewer"))
    assert response.status_code == 403


def test_dashboard_uses_actual_persisted_supplier_count(client, base_records):
    data = client.get("/api/dashboard").json()
    assert data["metrics"]["active_suppliers"] == 1
    assert data["fictional_demo"] is True


def test_operations_report_date_range_filters_invoice_metrics(client, base_records):
    supplier = base_records[0]
    from app.core.database import get_db
    session = client.app.dependency_overrides[get_db]().__next__()
    session.add_all([
        models.Invoice(number="INV-IN-RANGE", supplier_id=supplier.id, invoice_date=date(2025, 1, 15), due_date=date(2025, 2, 14), status="APPROVED", total_paise=1000),
        models.Invoice(number="INV-OUT-RANGE", supplier_id=supplier.id, invoice_date=date(2025, 2, 15), due_date=date(2025, 3, 17), status="APPROVED", total_paise=500),
    ])
    session.commit()
    response = client.get("/api/reports/operations?start=2025-01-01&end=2025-01-31")
    assert response.status_code == 200
    assert response.json()["invoice_count"] == 1
    assert response.json()["supplier_expenditure"] == [{"supplier": "Test Supplier", "total_paise": 1000}]


def test_operations_report_rejects_reversed_date_range(client):
    response = client.get("/api/reports/operations?start=2025-02-01&end=2025-01-01")
    assert response.status_code == 422


def test_reconciliation_balance_matches_payment_sum(client, base_records):
    supplier = base_records[0]
    inv = models.Invoice(number="INV-RECON", supplier_id=supplier.id, invoice_date=date.today(), due_date=date.today(), status="APPROVED", total_paise=1000)
    from app.core.database import get_db
    session = client.app.dependency_overrides[get_db]().__next__()
    session.add(inv); session.flush()
    session.add(models.Payment(reference="PAY-RECON", invoice_id=inv.id, amount_paise=300, method="NEFT")); session.commit()
    row = next(x for x in client.get("/api/reports/reconciliation").json() if x["invoice_number"] == "INV-RECON")
    assert row["paid_paise"] == 300 and row["open_balance_paise"] == 700


def test_audit_event_written_for_supplier_creation(client):
    response = client.post("/api/suppliers", json={"code": "SUP-AUD", "name": "Audited Supplier", "email": "audit@example.com"}, headers=auth(client, "procurement"))
    assert response.status_code == 201
    from app.core.database import get_db
    session = client.app.dependency_overrides[get_db]().__next__()
    assert session.query(models.AuditEvent).filter_by(entity_type="supplier", entity_id=response.json()["id"]).count() == 1


def test_invoice_change_restricted_after_approval(client, base_records):
    supplier = base_records[0]
    inv = models.Invoice(number="INV-LOCK", supplier_id=supplier.id, invoice_date=date.today(), due_date=date.today(), status="APPROVED", total_paise=100)
    from app.core.database import get_db
    session = client.app.dependency_overrides[get_db]().__next__()
    session.add(inv); session.commit()
    response = client.patch(f"/api/invoices/{inv.id}", json={"reported_tax_paise": 1}, headers=auth(client, "ap"))
    assert response.status_code == 409


def test_resolving_exception_does_not_approve_invoice(client, base_records):
    supplier = base_records[0]
    inv = models.Invoice(number="INV-EX", supplier_id=supplier.id, invoice_date=date.today(), due_date=date.today(), status="EXCEPTION", match_outcome="EXCEPTION", total_paise=100)
    from app.core.database import get_db
    session = client.app.dependency_overrides[get_db]().__next__()
    session.add(inv); session.flush()
    exc = models.ExceptionRecord(invoice_id=inv.id, category="MISSING_PO", description="No PO")
    session.add(exc); session.commit()
    response = client.post(f"/api/exceptions/{exc.id}/resolve", json={"resolution": "Confirmed as a non-PO service purchase"}, headers=auth(client, "ap"))
    assert response.status_code == 200 and response.json()["invoice"]["status"] == "EXCEPTION"


def test_repeated_po_approval_rejected(client, base_records):
    po = base_records[2]
    # First approve a draft purchase order.
    po.status = "DRAFT"
    response = client.post(f"/api/purchase-orders/{po.id}/approve", headers=auth(client, "approver"))
    assert response.status_code == 200
    assert client.post(f"/api/purchase-orders/{po.id}/approve", headers=auth(client, "approver")).status_code == 409
