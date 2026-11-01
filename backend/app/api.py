import csv
import base64
import hashlib
import hmac
import io
import json
import os
import secrets
import time
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.services import audit, extended_paise, match_invoice, matched_paid, quantity_milli, refresh_invoice_match, store_invoice_lines, update_payment_state

router = APIRouter(prefix="/api")
bearer = HTTPBearer(auto_error=False)
# Generate a process-local key for offline demo runs. Set P2P_SESSION_SECRET to
# preserve sessions across restarts or share a key between multiple workers.
TOKEN_SECRET = os.getenv("P2P_SESSION_SECRET") or secrets.token_urlsafe(32)


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"{base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(derived).decode()}"


def password_matches(password: str, value: str) -> bool:
    try:
        salt_text, expected_text = value.split("$", 1)
        salt = base64.urlsafe_b64decode(salt_text)
        actual = password_hash(password, salt).split("$", 1)[1]
        return hmac.compare_digest(actual, expected_text)
    except (ValueError, TypeError):
        return False


def issue_token(user: models.UserAccount) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"sub": user.username, "exp": int(time.time()) + 8 * 60 * 60}, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(TOKEN_SECRET.encode(), payload.encode(), hashlib.sha256).digest()
    return f"{payload}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"


def resolve_user(credentials: HTTPAuthorizationCredentials | None, db: Session):
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Sign in to perform this action", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload, signature = credentials.credentials.split(".", 1)
        expected = base64.urlsafe_b64encode(hmac.new(TOKEN_SECRET.encode(), payload.encode(), hashlib.sha256).digest()).decode().rstrip("=")
        if not hmac.compare_digest(expected, signature):
            raise ValueError("bad signature")
        raw = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        claims = json.loads(raw)
        if int(claims["exp"]) < int(time.time()):
            raise ValueError("expired")
        user = db.query(models.UserAccount).filter_by(username=claims["sub"], active=True).first()
        if not user:
            raise ValueError("inactive")
        return user
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(401, "Session is invalid or expired", headers={"WWW-Authenticate": "Bearer"})


def authenticated(db: Session = Depends(get_db), credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    return resolve_user(credentials, db)


def require_role(*roles):
    def check(db: Session = Depends(get_db), credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        user = resolve_user(credentials, db)
        if user.role.lower() not in roles and user.role.lower() != "admin":
            raise HTTPException(403, f"Role '{user.role}' cannot perform this action")
        return user
    return check


def supplier_view(s):
    return {"id": s.id, "code": s.code, "name": s.name, "contact_person": s.contact_person, "email": s.email, "phone": s.phone,
            "address": s.address, "gstin": s.gstin, "pan": s.pan, "payment_terms_days": s.payment_terms_days, "active": s.active,
            "fictional": s.fictional, "created_at": s.created_at}


def invoice_view(db: Session, x: models.Invoice):
    return {"id": x.id, "number": x.number, "supplier_id": x.supplier_id, "supplier_name": x.supplier.name,
            "purchase_order_id": x.purchase_order_id, "po_number": db.get(models.PurchaseOrder, x.purchase_order_id).number if x.purchase_order_id and db.get(models.PurchaseOrder, x.purchase_order_id) else None,
            "invoice_date": x.invoice_date, "due_date": x.due_date, "status": x.status, "match_outcome": x.match_outcome, "matching_mode": x.matching_mode,
            "subtotal_paise": x.subtotal_paise, "tax_paise": x.tax_paise, "total_paise": x.total_paise,
            "paid_paise": matched_paid(db, x), "balance_paise": x.total_paise - matched_paid(db, x),
            "lines": [{"id": l.id, "purchase_order_line_id": l.purchase_order_line_id, "description": l.description,
                       "quantity_milli": l.quantity_milli, "unit_price_paise": l.unit_price_paise,
                       "tax_rate_bps": l.tax_rate_bps, "subtotal_paise": l.subtotal_paise, "tax_paise": l.tax_paise} for l in x.lines]}


def po_view(po):
    subtotal = sum(extended_paise(l.unit_price_paise, Decimal(l.quantity_milli) / 1000) for l in po.lines)
    return {"id": po.id, "number": po.number, "supplier_id": po.supplier_id, "supplier_name": po.supplier.name,
            "requisition_id": po.requisition_id, "status": po.status, "ordered_on": po.ordered_on, "expected_on": po.expected_on,
            "subtotal_paise": subtotal, "lines": [{"id": l.id, "line_no": l.line_no, "description": l.description,
            "quantity_milli": l.quantity_milli, "unit_price_paise": l.unit_price_paise, "tax_rate_bps": l.tax_rate_bps} for l in po.lines]}


@router.get("/health")
def health():
    return {"status": "ok", "application": "ERP P2P Reconciliation Simulation"}


@router.get("/auth/demo-accounts")
def demo_accounts():
    return {"local_demo": True, "accounts": ["requester", "procurement", "receiving", "ap", "approver", "admin"],
            "password_pattern": "demo-<username>"}


@router.post("/auth/login")
def login(body: schemas.LoginInput, db: Session = Depends(get_db)):
    user = db.query(models.UserAccount).filter_by(username=body.username.lower(), active=True).first()
    if not user or not password_matches(body.password, user.password_hash):
        raise HTTPException(401, "Invalid username or password")
    return {"access_token": issue_token(user), "token_type": "bearer", "expires_in": 28800,
            "user": {"username": user.username, "role": user.role}}


@router.get("/suppliers")
def suppliers(search: str = "", active: bool | None = None, db: Session = Depends(get_db), _=Depends(authenticated)):
    q = db.query(models.Supplier)
    if search:
        q = q.filter(models.Supplier.name.ilike(f"%{search}%") | models.Supplier.code.ilike(f"%{search}%"))
    if active is not None:
        q = q.filter_by(active=active)
    return [supplier_view(s) for s in q.order_by(models.Supplier.name).all()]


@router.post("/suppliers", status_code=201)
def create_supplier(body: schemas.SupplierCreate, db: Session = Depends(get_db), user=Depends(require_role("procurement", "admin"))):
    if db.query(models.Supplier).filter((models.Supplier.code == body.code) | (models.Supplier.email == str(body.email))).first():
        raise HTTPException(409, "Supplier code or email already exists")
    values = body.model_dump()
    values["email"] = str(body.email)
    values["gstin"] = values["gstin"] or None
    values["pan"] = values["pan"] or None
    item = models.Supplier(**values)
    db.add(item)
    db.flush()
    audit(db, "supplier", item.id, "CREATED", f"Supplier {item.code} registered", user.username)
    db.commit()
    db.refresh(item)
    return supplier_view(item)


@router.patch("/suppliers/{supplier_id}")
def update_supplier(supplier_id: int, body: schemas.SupplierUpdate, db: Session = Depends(get_db), user=Depends(require_role("procurement", "admin"))):
    item = db.get(models.Supplier, supplier_id)
    if not item:
        raise HTTPException(404, "Supplier not found")
    values = body.model_dump(exclude_unset=True)
    if "email" in values and db.query(models.Supplier).filter(models.Supplier.id != item.id, models.Supplier.email == str(values["email"])).first():
        raise HTTPException(409, "Supplier email already exists")
    if "gstin" in values and values["gstin"] and db.query(models.Supplier).filter(models.Supplier.id != item.id, models.Supplier.gstin == values["gstin"]).first():
        raise HTTPException(409, "GSTIN is already registered")
    for key, value in values.items():
        if key in {"gstin", "pan"} and value == "":
            value = None
        setattr(item, key, str(value) if key == "email" and value else value)
    audit(db, "supplier", item.id, "UPDATED", "Supplier profile updated", user.username)
    db.commit()
    return supplier_view(item)


@router.get("/suppliers/{supplier_id}/history")
def supplier_history(supplier_id: int, db: Session = Depends(get_db), _=Depends(authenticated)):
    supplier = db.get(models.Supplier, supplier_id)
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    pos = db.query(models.PurchaseOrder).filter_by(supplier_id=supplier.id).order_by(models.PurchaseOrder.ordered_on.desc()).all()
    invs = db.query(models.Invoice).filter_by(supplier_id=supplier.id).order_by(models.Invoice.invoice_date.desc()).all()
    return {"supplier": supplier_view(supplier), "purchase_orders": [{"number": x.number, "status": x.status, "ordered_on": x.ordered_on} for x in pos],
            "invoices": [{"number": x.number, "status": x.status, "total_paise": x.total_paise, "due_date": x.due_date} for x in invs],
            "payments": [{"reference": p.reference, "invoice_number": db.get(models.Invoice, p.invoice_id).number, "amount_paise": p.amount_paise, "paid_on": p.paid_on}
                         for inv in invs for p in db.query(models.Payment).filter_by(invoice_id=inv.id).all()]}


@router.get("/requisitions")
def requisitions(db: Session = Depends(get_db), _=Depends(authenticated)):
    return [{"id": r.id, "number": r.number, "requester": r.requester, "department": r.department,
             "description": r.description, "status": r.status, "requested_at": r.requested_at,
             "lines": [{"description": l.description, "quantity_milli": l.quantity_milli,
                        "estimated_unit_price_paise": l.estimated_unit_price_paise} for l in r.lines]}
            for r in db.query(models.Requisition).order_by(models.Requisition.requested_at.desc()).all()]


@router.post("/requisitions", status_code=201)
def create_requisition(body: schemas.RequisitionCreate, db: Session = Depends(get_db), user=Depends(require_role("requester", "procurement", "admin"))):
    item = models.Requisition(number=f"REQ-{date.today():%y%m%d}-{db.query(models.Requisition).count()+1:04d}", requester=body.requester,
                              department=body.department, description=body.description, status="SUBMITTED")
    for line in body.lines:
        item.lines.append(models.RequisitionLine(description=line.description, quantity_milli=quantity_milli(line.quantity), estimated_unit_price_paise=line.unit_price_paise))
    db.add(item)
    db.flush()
    audit(db, "requisition", item.id, "SUBMITTED", "Submitted for approval", user.username)
    db.commit()
    return {"id": item.id, "number": item.number, "status": item.status}


@router.post("/requisitions/{requisition_id}/decision")
def requisition_decision(requisition_id: int, body: schemas.DecisionInput, db: Session = Depends(get_db), user=Depends(require_role("approver", "admin"))):
    item = db.get(models.Requisition, requisition_id)
    if not item:
        raise HTTPException(404, "Requisition not found")
    if item.status != "SUBMITTED":
        raise HTTPException(409, "Only submitted requisitions can be decided")
    item.status = body.decision
    db.add(models.Approval(entity_type="REQUISITION", entity_id=item.id, approver=user.username, decision=body.decision, comment=body.comment))
    audit(db, "requisition", item.id, body.decision, body.comment, user.username)
    db.commit()
    return {"id": item.id, "status": item.status}


@router.get("/purchase-orders")
def purchase_orders(db: Session = Depends(get_db), _=Depends(authenticated)):
    return [po_view(po) for po in db.query(models.PurchaseOrder).order_by(models.PurchaseOrder.ordered_on.desc()).all()]


@router.post("/purchase-orders", status_code=201)
def create_po(body: schemas.PurchaseOrderCreate, db: Session = Depends(get_db), user=Depends(require_role("procurement", "admin"))):
    supplier = db.get(models.Supplier, body.supplier_id)
    if not supplier or not supplier.active:
        raise HTTPException(422, "Select an active supplier")
    req = db.get(models.Requisition, body.requisition_id) if body.requisition_id else None
    if body.requisition_id and (not req or req.status != "APPROVED"):
        raise HTTPException(409, "Purchase order requires an approved requisition")
    po = models.PurchaseOrder(number=f"PO-{date.today():%y%m%d}-{db.query(models.PurchaseOrder).count()+1:04d}", supplier_id=supplier.id,
                             requisition_id=req.id if req else None, status="DRAFT", expected_on=body.expected_on)
    for idx, line in enumerate(body.lines, 1):
        po.lines.append(models.PurchaseOrderLine(line_no=idx, description=line.description, quantity_milli=quantity_milli(line.quantity), unit_price_paise=line.unit_price_paise, tax_rate_bps=line.tax_rate_bps))
    db.add(po)
    db.flush()
    audit(db, "purchase_order", po.id, "CREATED", "Purchase order drafted", user.username)
    db.commit()
    return po_view(po)


@router.post("/purchase-orders/{po_id}/approve")
def approve_po(po_id: int, db: Session = Depends(get_db), user=Depends(require_role("approver", "admin"))):
    po = db.get(models.PurchaseOrder, po_id)
    if not po:
        raise HTTPException(404, "Purchase order not found")
    if po.status != "DRAFT":
        raise HTTPException(409, "Only draft purchase orders can be approved")
    po.status = "OPEN"
    db.add(models.Approval(entity_type="PURCHASE_ORDER", entity_id=po.id, approver=user.username, decision="APPROVED"))
    audit(db, "purchase_order", po.id, "APPROVED", "Order released to supplier", user.username)
    db.commit()
    return {"id": po.id, "status": po.status}


@router.get("/goods-receipts")
def goods_receipts(db: Session = Depends(get_db), _=Depends(authenticated)):
    return [{"id": x.id, "number": x.number, "purchase_order_id": x.purchase_order_id,
             "po_number": db.get(models.PurchaseOrder, x.purchase_order_id).number, "received_on": x.received_on,
             "received_by": x.received_by, "status": x.status,
             "lines": [{"purchase_order_line_id": l.purchase_order_line_id, "received_quantity_milli": l.received_quantity_milli,
                        "accepted_quantity_milli": l.accepted_quantity_milli, "rejected_quantity_milli": l.rejected_quantity_milli} for l in x.lines]}
            for x in db.query(models.GoodsReceipt).order_by(models.GoodsReceipt.received_on.desc()).all()]


@router.post("/goods-receipts", status_code=201)
def create_receipt(body: schemas.ReceiptCreate, db: Session = Depends(get_db), user=Depends(require_role("receiving", "admin"))):
    po = db.get(models.PurchaseOrder, body.purchase_order_id)
    if not po or po.status not in {"OPEN", "PARTIALLY_RECEIVED"}:
        raise HTTPException(409, "Goods can only be received against an open purchase order")
    receipt = models.GoodsReceipt(number=f"GRN-{date.today():%y%m%d}-{db.query(models.GoodsReceipt).count()+1:04d}", purchase_order_id=po.id,
                                  received_on=body.received_on, received_by=body.received_by)
    received_in_request: dict[int, int] = {}
    for line in body.lines:
        po_line = db.get(models.PurchaseOrderLine, line.purchase_order_line_id)
        if not po_line or po_line.purchase_order_id != po.id:
            raise HTTPException(422, "Receipt line must reference the selected purchase order")
        received = quantity_milli(line.received_quantity)
        accepted = quantity_milli(line.accepted_quantity)
        if accepted > received:
            raise HTTPException(422, "Accepted quantity cannot exceed received quantity")
        prior = db.query(func.coalesce(func.sum(models.GoodsReceiptLine.received_quantity_milli), 0)).filter_by(purchase_order_line_id=po_line.id).scalar() or 0
        received_in_request[po_line.id] = received_in_request.get(po_line.id, 0) + received
        if prior + received_in_request[po_line.id] > po_line.quantity_milli:
            raise HTTPException(409, "Cumulative received quantity cannot exceed ordered quantity")
        receipt.lines.append(models.GoodsReceiptLine(purchase_order_line_id=po_line.id, received_quantity_milli=received,
            accepted_quantity_milli=accepted, rejected_quantity_milli=received-accepted))
    db.add(receipt)
    db.flush()
    any_remaining = False
    for po_line in po.lines:
        total_received = db.query(func.coalesce(func.sum(models.GoodsReceiptLine.received_quantity_milli), 0)).join(models.GoodsReceipt).filter(models.GoodsReceiptLine.purchase_order_line_id == po_line.id).scalar() or 0
        any_remaining |= total_received < po_line.quantity_milli
    po.status = "PARTIALLY_RECEIVED" if any_remaining else "RECEIVED"
    audit(db, "goods_receipt", receipt.id, "RECORDED", f"Receipt recorded against {po.number}", user.username)
    db.commit()
    return {"id": receipt.id, "number": receipt.number, "purchase_order_status": po.status}


@router.get("/invoices")
def invoices(status: str | None = None, search: str = "", db: Session = Depends(get_db), _=Depends(authenticated)):
    q = db.query(models.Invoice)
    if status:
        q = q.filter_by(status=status.upper())
    if search:
        q = q.filter(models.Invoice.number.ilike(f"%{search}%"))
    return [invoice_view(db, x) for x in q.order_by(models.Invoice.due_date).all()]


@router.post("/invoices", status_code=201)
def create_invoice(body: schemas.InvoiceCreate, db: Session = Depends(get_db), user=Depends(require_role("ap", "admin"))):
    normalized_number = body.number.strip().upper()
    if db.query(models.Invoice).filter(models.Invoice.supplier_id == body.supplier_id, func.lower(models.Invoice.number) == normalized_number.lower()).first():
        raise HTTPException(409, "Duplicate supplier invoice number")
    if body.due_date < body.invoice_date:
        raise HTTPException(422, "Due date cannot precede invoice date")
    supplier = db.get(models.Supplier, body.supplier_id)
    if not supplier:
        raise HTTPException(422, "Supplier not found")
    if body.purchase_order_id:
        po = db.get(models.PurchaseOrder, body.purchase_order_id)
        if not po or po.supplier_id != supplier.id or po.status not in {"OPEN", "PARTIALLY_RECEIVED", "RECEIVED"}:
            raise HTTPException(422, "Purchase order must belong to the selected supplier")
    invoice = models.Invoice(number=normalized_number, supplier_id=supplier.id, purchase_order_id=body.purchase_order_id,
                             invoice_date=body.invoice_date, due_date=body.due_date, matching_mode=body.matching_mode)
    store_invoice_lines(invoice, body.lines)
    if body.reported_tax_paise is not None:
        invoice.tax_paise = body.reported_tax_paise
        invoice.total_paise = invoice.subtotal_paise + invoice.tax_paise
    db.add(invoice)
    db.flush()
    findings = refresh_invoice_match(db, invoice)
    audit(db, "invoice", invoice.id, "RECEIVED", f"Matching result: {invoice.match_outcome}; {len(findings)} finding(s)", user.username)
    db.commit()
    return invoice_view(db, invoice)


@router.patch("/invoices/{invoice_id}")
def update_invoice(invoice_id: int, body: schemas.InvoiceUpdate, db: Session = Depends(get_db), user=Depends(require_role("ap", "admin"))):
    invoice = db.get(models.Invoice, invoice_id)
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if invoice.status in {"APPROVED", "PARTIALLY_PAID", "PAID", "REJECTED"}:
        raise HTTPException(409, "Only unapproved invoices may be corrected")
    values = body.model_dump(exclude_unset=True)
    lines = values.pop("lines", None)
    reported_tax = values.pop("reported_tax_paise", None)
    has_reported_tax = "reported_tax_paise" in body.model_fields_set
    if "purchase_order_id" in values:
        po_id = values["purchase_order_id"]
        po = db.get(models.PurchaseOrder, po_id) if po_id is not None else None
        if po_id is not None and (not po or po.supplier_id != invoice.supplier_id or po.status not in {"OPEN", "PARTIALLY_RECEIVED", "RECEIVED"}):
            raise HTTPException(422, "Purchase order must belong to the selected supplier")
    for key, value in values.items():
        setattr(invoice, key, value)
    if invoice.due_date < invoice.invoice_date:
        raise HTTPException(422, "Due date cannot precede invoice date")
    if lines is not None:
        invoice.lines.clear()
        db.flush()
        store_invoice_lines(invoice, lines)
    if reported_tax is not None:
        invoice.tax_paise = reported_tax
        invoice.total_paise = invoice.subtotal_paise + reported_tax
    elif has_reported_tax:
        invoice.tax_paise = sum(line.tax_paise for line in invoice.lines)
        invoice.total_paise = invoice.subtotal_paise + invoice.tax_paise
    refresh_invoice_match(db, invoice)
    audit(db, "invoice", invoice.id, "CORRECTED", "Invoice details corrected", user.username)
    db.commit()
    return invoice_view(db, invoice)


@router.post("/invoices/{invoice_id}/match")
def run_match(invoice_id: int, db: Session = Depends(get_db), user=Depends(require_role("ap", "approver", "admin"))):
    invoice = db.get(models.Invoice, invoice_id)
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    findings = refresh_invoice_match(db, invoice)
    audit(db, "invoice", invoice.id, "MATCHED", f"Matching result: {invoice.match_outcome}; {len(findings)} finding(s)", user.username)
    db.commit()
    return {"invoice": invoice_view(db, invoice), "findings": [{"category": k, "description": d} for k, d in findings]}


@router.post("/invoices/{invoice_id}/decision")
def invoice_decision(invoice_id: int, body: schemas.DecisionInput, db: Session = Depends(get_db), user=Depends(require_role("approver", "admin"))):
    invoice = db.get(models.Invoice, invoice_id)
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if body.decision == "APPROVED" and (invoice.match_outcome != "MATCHED" or db.query(models.ExceptionRecord).filter_by(invoice_id=invoice.id, status="OPEN").count()):
        raise HTTPException(409, "Invoice must have a clean match and no open exceptions before approval")
    if invoice.status not in {"PENDING_APPROVAL", "EXCEPTION"}:
        raise HTTPException(409, "Invoice is not awaiting a decision")
    invoice.status = "APPROVED" if body.decision == "APPROVED" else "REJECTED"
    if body.decision == "APPROVED":
        invoice.match_outcome = "APPROVED"
    db.add(models.Approval(entity_type="INVOICE", entity_id=invoice.id, approver=user.username, decision=body.decision, comment=body.comment))
    audit(db, "invoice", invoice.id, body.decision, body.comment, user.username)
    db.commit()
    return invoice_view(db, invoice)


@router.get("/exceptions")
def exceptions(status: str | None = "OPEN", db: Session = Depends(get_db), _=Depends(authenticated)):
    q = db.query(models.ExceptionRecord)
    if status:
        q = q.filter_by(status=status.upper())
    return [{"id": x.id, "invoice_id": x.invoice_id, "invoice_number": db.get(models.Invoice, x.invoice_id).number,
             "category": x.category, "description": x.description, "status": x.status, "resolution": x.resolution,
             "created_at": x.created_at} for x in q.order_by(models.ExceptionRecord.created_at.desc()).all()]


@router.post("/exceptions/{exception_id}/resolve")
def resolve_exception(exception_id: int, body: schemas.ResolveInput, db: Session = Depends(get_db), user=Depends(require_role("ap", "approver", "admin"))):
    item = db.get(models.ExceptionRecord, exception_id)
    if not item:
        raise HTTPException(404, "Exception not found")
    if item.status != "OPEN":
        raise HTTPException(409, "Exception is already resolved")
    item.status = "RESOLVED"
    item.resolution = body.resolution
    item.resolved_at = models.utc_now()
    audit(db, "exception", item.id, "RESOLVED", body.resolution, user.username)
    db.commit()
    invoice = db.get(models.Invoice, item.invoice_id)
    return {"id": item.id, "status": item.status, "invoice": invoice_view(db, invoice)}


@router.get("/payments")
def payments(db: Session = Depends(get_db), _=Depends(authenticated)):
    return [{"id": p.id, "reference": p.reference, "invoice_id": p.invoice_id,
             "invoice_number": db.get(models.Invoice, p.invoice_id).number, "supplier_name": db.get(models.Invoice, p.invoice_id).supplier.name,
             "paid_on": p.paid_on, "amount_paise": p.amount_paise, "method": p.method, "note": p.note}
            for p in db.query(models.Payment).order_by(models.Payment.paid_on.desc()).all()]


@router.post("/payments", status_code=201)
def create_payment(body: schemas.PaymentCreate, db: Session = Depends(get_db), user=Depends(require_role("ap", "admin"))):
    invoice = db.get(models.Invoice, body.invoice_id)
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if invoice.status not in {"APPROVED", "PARTIALLY_PAID"}:
        raise HTTPException(409, "Only approved invoices with an unpaid balance can be paid")
    paid = matched_paid(db, invoice)
    if paid + body.amount_paise > invoice.total_paise:
        raise HTTPException(409, "Payment exceeds the remaining approved invoice balance")
    payment = models.Payment(reference=f"PAY-{date.today():%y%m%d}-{db.query(models.Payment).count()+1:04d}", invoice_id=invoice.id,
                             paid_on=body.paid_on, amount_paise=body.amount_paise, method=body.method, note=body.note)
    db.add(payment)
    db.flush()
    update_payment_state(db, invoice)
    audit(db, "invoice", invoice.id, "PAYMENT_RECORDED", f"{payment.reference}: {body.amount_paise} paise", user.username)
    db.commit()
    return {"id": payment.id, "reference": payment.reference, "invoice": invoice_view(db, invoice)}


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _=Depends(authenticated)):
    today = date.today()
    invoices = db.query(models.Invoice).all()
    suppliers_count = db.query(models.Supplier).filter_by(active=True).count()
    open_pos = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.status.in_(["OPEN", "PARTIALLY_RECEIVED"])).count()
    open_exceptions = db.query(models.ExceptionRecord).filter_by(status="OPEN").count()
    outstanding = sum(max(0, inv.total_paise - matched_paid(db, inv)) for inv in invoices if inv.status in {"APPROVED", "PARTIALLY_PAID"})
    overdue = sum(max(0, inv.total_paise - matched_paid(db, inv)) for inv in invoices if inv.due_date < today and inv.status in {"APPROVED", "PARTIALLY_PAID"})
    month_labels = []
    monthly = []
    for offset in range(5, -1, -1):
        month_index = today.year * 12 + today.month - 1 - offset
        year, month_zero = divmod(month_index, 12)
        first = date(year, month_zero + 1, 1)
        label = first.strftime("%b %y")
        month_labels.append(label)
        amount = sum(x.total_paise for x in invoices if x.invoice_date.year == first.year and x.invoice_date.month == first.month)
        monthly.append({"month": label, "amount_paise": amount})
    recent = sorted(invoices, key=lambda x: x.created_at, reverse=True)[:6]
    return {"as_of": today.isoformat(), "fictional_demo": True, "metrics": {"active_suppliers": suppliers_count,
            "open_purchase_orders": open_pos, "open_exceptions": open_exceptions, "outstanding_paise": outstanding, "overdue_paise": overdue,
            "pending_approvals": db.query(models.Invoice).filter_by(status="PENDING_APPROVAL").count()},
            "monthly_spend": monthly, "recent_invoices": [invoice_view(db, x) for x in recent]}


@router.get("/reports/reconciliation")
def reconciliation(db: Session = Depends(get_db), _=Depends(authenticated)):
    out = []
    for inv in db.query(models.Invoice).order_by(models.Invoice.due_date).all():
        paid = matched_paid(db, inv)
        out.append({"invoice_id": inv.id, "invoice_number": inv.number, "supplier": inv.supplier.name,
                    "invoice_total_paise": inv.total_paise, "paid_paise": paid, "open_balance_paise": inv.total_paise-paid,
                    "status": inv.status, "due_date": inv.due_date})
    return out


@router.get("/export/{kind}.csv")
def export_csv(kind: str, db: Session = Depends(get_db), _=Depends(authenticated)):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    if kind == "suppliers":
        writer.writerow(["code", "name", "contact_person", "email", "phone", "address", "gstin", "pan", "payment_terms_days", "active"])
        for s in db.query(models.Supplier).order_by(models.Supplier.code):
            writer.writerow([s.code, s.name, s.contact_person, s.email, s.phone, s.address, s.gstin or "", s.pan or "", s.payment_terms_days, s.active])
    elif kind == "invoices":
        writer.writerow(["invoice_number", "supplier", "po_number", "invoice_date", "due_date", "status", "subtotal_paise", "tax_paise", "total_paise", "paid_paise", "balance_paise"])
        for inv in db.query(models.Invoice).order_by(models.Invoice.invoice_date):
            writer.writerow([inv.number, inv.supplier.name, db.get(models.PurchaseOrder, inv.purchase_order_id).number if inv.purchase_order_id else "", inv.invoice_date,
                inv.due_date, inv.status, inv.subtotal_paise, inv.tax_paise, inv.total_paise, matched_paid(db, inv), inv.total_paise-matched_paid(db, inv)])
    elif kind == "exceptions":
        writer.writerow(["invoice_number", "category", "description", "status", "resolution"])
        for e in db.query(models.ExceptionRecord):
            writer.writerow([db.get(models.Invoice, e.invoice_id).number, e.category, e.description, e.status, e.resolution or ""])
    elif kind == "payments":
        writer.writerow(["reference", "invoice_number", "supplier", "paid_on", "amount_paise", "method"])
        for p in db.query(models.Payment):
            inv = db.get(models.Invoice, p.invoice_id)
            writer.writerow([p.reference, inv.number, inv.supplier.name, p.paid_on, p.amount_paise, p.method])
    elif kind == "purchase-orders":
        writer.writerow(["po_number", "supplier", "requisition_id", "status", "ordered_on", "expected_on", "subtotal_paise"])
        for po in db.query(models.PurchaseOrder).order_by(models.PurchaseOrder.ordered_on):
            writer.writerow([po.number, po.supplier.name, po.requisition_id or "", po.status, po.ordered_on, po.expected_on or "",
                             sum(extended_paise(l.unit_price_paise, Decimal(l.quantity_milli)/1000) for l in po.lines)])
    elif kind == "reconciliation":
        writer.writerow(["invoice_number", "supplier", "invoice_total_paise", "paid_paise", "open_balance_paise", "status", "due_date"])
        for inv in db.query(models.Invoice).order_by(models.Invoice.due_date):
            paid = matched_paid(db, inv)
            writer.writerow([inv.number, inv.supplier.name, inv.total_paise, paid, inv.total_paise-paid, inv.status, inv.due_date])
    else:
        raise HTTPException(404, "CSV export type not supported")
    return Response(buffer.getvalue(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={kind}.csv"})


@router.get("/reports/operations")
def operations_report(start: date | None = None, end: date | None = None, db: Session = Depends(get_db), _=Depends(authenticated)):
    if start and end and end < start:
        raise HTTPException(422, "End date cannot precede start date")
    invoice_query = db.query(models.Invoice)
    if start:
        invoice_query = invoice_query.filter(models.Invoice.invoice_date >= start)
    if end:
        invoice_query = invoice_query.filter(models.Invoice.invoice_date <= end)
    invoices = invoice_query.all()
    included = {x.id for x in invoices}
    supplier_spend = {}
    invoice_status = {}
    matching_outcomes = {}
    for inv in invoices:
        supplier_spend[inv.supplier.name] = supplier_spend.get(inv.supplier.name, 0) + inv.total_paise
        invoice_status[inv.status] = invoice_status.get(inv.status, 0) + 1
        matching_outcomes[inv.match_outcome] = matching_outcomes.get(inv.match_outcome, 0) + 1
    exceptions_query = db.query(models.ExceptionRecord)
    if included:
        exceptions_query = exceptions_query.filter(models.ExceptionRecord.invoice_id.in_(included))
    elif start or end:
        exceptions_query = exceptions_query.filter(models.ExceptionRecord.invoice_id == -1)
    category_counts = {}
    for item in exceptions_query.all():
        category_counts[item.category] = category_counts.get(item.category, 0) + 1
    pos = db.query(models.PurchaseOrder).all()
    receipts = db.query(models.GoodsReceipt).all()
    outstanding = sum(max(0, inv.total_paise-matched_paid(db, inv)) for inv in invoices if inv.status in {"APPROVED", "PARTIALLY_PAID"})
    overdue = [{"invoice_number": inv.number, "supplier": inv.supplier.name, "due_date": inv.due_date.isoformat(), "balance_paise": inv.total_paise-matched_paid(db, inv)}
               for inv in invoices if inv.due_date < date.today() and inv.status in {"APPROVED", "PARTIALLY_PAID"} and inv.total_paise > matched_paid(db, inv)]
    return {"date_range": {"start": start.isoformat() if start else None, "end": end.isoformat() if end else None},
            "supplier_expenditure": sorted([{"supplier": k, "total_paise": v} for k, v in supplier_spend.items()], key=lambda x: -x["total_paise"]),
            "purchase_order_status": _count_by(pos, "status"), "goods_receipt_status": _count_by(receipts, "status"),
            "invoice_status": invoice_status, "matching_outcomes": matching_outcomes, "exception_categories": category_counts,
            "pending_approvals": db.query(models.Approval).filter_by(decision="PENDING").count() + sum(1 for x in invoices if x.status == "PENDING_APPROVAL"),
            "outstanding_paise": outstanding, "overdue_invoices": overdue, "invoice_count": len(invoices)}


def _count_by(records, field):
    counts = {}
    for row in records:
        value = getattr(row, field)
        counts[value] = counts.get(value, 0) + 1
    return counts


@router.post("/suppliers/import.csv")
async def import_suppliers(file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(require_role("procurement", "admin"))):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(415, "Upload a CSV file")
    try:
        raw_content = await file.read(5 * 1024 * 1024 + 1)
        if len(raw_content) > 5 * 1024 * 1024:
            raise HTTPException(413, "CSV uploads are limited to 5 MiB")
        content = raw_content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
    except UnicodeDecodeError:
        raise HTTPException(400, "CSV must use UTF-8 encoding")
    required = {"code", "name", "email"}
    if not required.issubset(set(reader.fieldnames or [])):
        raise HTTPException(422, "CSV requires code, name, and email columns")
    created, errors, seen = [], [], set()
    for row_number, row in enumerate(reader, start=2):
        code = (row.get("code") or "").strip()
        email = (row.get("email") or "").strip().lower()
        try:
            if not code or not (row.get("name") or "").strip():
                raise ValueError("code and name are required")
            validate_email(email, check_deliverability=False)
        except (ValueError, EmailNotValidError) as exc:
            errors.append({"row": row_number, "error": str(exc)})
            continue
        if code.lower() in seen or db.query(models.Supplier).filter((models.Supplier.code == code) | (models.Supplier.email == email)).first():
            errors.append({"row": row_number, "error": "duplicate supplier code or email"})
            continue
        try:
            terms = int(row.get("payment_terms_days") or 30)
            if not 0 <= terms <= 180:
                raise ValueError("payment_terms_days must be between 0 and 180")
        except ValueError as exc:
            errors.append({"row": row_number, "error": str(exc)})
            continue
        gstin = (row.get("gstin") or "").strip().upper() or None
        pan = (row.get("pan") or "").strip().upper() or None
        if gstin and (len(gstin) != 15 or db.query(models.Supplier).filter_by(gstin=gstin).first()):
            errors.append({"row": row_number, "error": "GSTIN must be unique and contain 15 characters"})
            continue
        if pan and len(pan) != 10:
            errors.append({"row": row_number, "error": "PAN must contain 10 characters"})
            continue
        seen.add(code.lower())
        item = models.Supplier(code=code, name=row["name"].strip(), email=email, contact_person=(row.get("contact_person") or "").strip(),
            phone=(row.get("phone") or "").strip(), address=(row.get("address") or "").strip(), gstin=gstin,
            pan=pan, payment_terms_days=terms)
        db.add(item)
        db.flush()
        audit(db, "supplier", item.id, "IMPORTED", f"Imported from {file.filename}", user.username)
        created.append(item.code)
    db.commit()
    return {"created": created, "created_count": len(created), "errors": errors}
