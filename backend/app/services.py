from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models


def quantity_milli(value: Decimal) -> int:
    scaled = value * 1000
    if scaled != scaled.to_integral_value():
        raise ValueError("Quantity supports up to three decimal places")
    return int(scaled)


def extended_paise(unit_price_paise: int, quantity: Decimal) -> int:
    return int((Decimal(unit_price_paise) * quantity).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def tax_paise(subtotal: int, rate_bps: int) -> int:
    return int((Decimal(subtotal) * Decimal(rate_bps) / Decimal(10000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def audit(db: Session, entity_type: str, entity_id: int, action: str, detail: str = "", actor: str = "Demo User"):
    db.add(models.AuditEvent(entity_type=entity_type, entity_id=entity_id, action=action, detail=detail, actor=actor))


def matched_paid(db: Session, invoice: models.Invoice) -> int:
    return db.query(func.coalesce(func.sum(models.Payment.amount_paise), 0)).filter(models.Payment.invoice_id == invoice.id).scalar() or 0


def match_invoice(db: Session, invoice: models.Invoice) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    duplicate = db.query(models.Invoice).filter(models.Invoice.id != invoice.id, models.Invoice.supplier_id == invoice.supplier_id, func.lower(models.Invoice.number) == invoice.number.lower()).first()
    if duplicate:
        findings.append(("DUPLICATE", f"Invoice number {invoice.number} already exists for this supplier."))
    po = db.get(models.PurchaseOrder, invoice.purchase_order_id) if invoice.purchase_order_id else None
    if not po:
        findings.append(("MISSING_PO", "No purchase order is linked to this invoice."))
    elif po.supplier_id != invoice.supplier_id:
        findings.append(("SUPPLIER_MISMATCH", "Invoice supplier does not match the purchase order supplier."))
    else:
        accepted_by_line: dict[int, int] = {}
        received_by_line: dict[int, int] = {}
        for receipt in db.query(models.GoodsReceipt).filter_by(purchase_order_id=po.id, status="ACCEPTED").all():
            for rline in receipt.lines:
                accepted_by_line[rline.purchase_order_line_id] = accepted_by_line.get(rline.purchase_order_line_id, 0) + rline.accepted_quantity_milli
                received_by_line[rline.purchase_order_line_id] = received_by_line.get(rline.purchase_order_line_id, 0) + rline.received_quantity_milli
        current_invoice_by_line: dict[int, int] = {}
        for line in invoice.lines:
            po_line = db.get(models.PurchaseOrderLine, line.purchase_order_line_id) if line.purchase_order_line_id else None
            if not po_line or po_line.purchase_order_id != po.id:
                findings.append(("UNMATCHED_LINE", f"Invoice line '{line.description}' is not linked to a line on the selected order."))
                continue
            if line.unit_price_paise != po_line.unit_price_paise:
                findings.append(("PRICE_VARIANCE", f"Invoice price differs from PO line {po_line.line_no}."))
            current_invoice_by_line[po_line.id] = current_invoice_by_line.get(po_line.id, 0) + line.quantity_milli
            invoiced_before = db.query(func.coalesce(func.sum(models.InvoiceLine.quantity_milli), 0)).join(models.Invoice).filter(models.InvoiceLine.purchase_order_line_id == po_line.id, models.Invoice.id != invoice.id, models.Invoice.status != "REJECTED").scalar() or 0
            if current_invoice_by_line[po_line.id] + invoiced_before > po_line.quantity_milli:
                findings.append(("PO_QUANTITY_VARIANCE", f"Invoiced quantity exceeds ordered quantity on PO line {po_line.line_no}."))
            if invoice.matching_mode == "THREE_WAY" and current_invoice_by_line[po_line.id] + invoiced_before > accepted_by_line.get(po_line.id, 0):
                findings.append(("RECEIPT_QUANTITY_VARIANCE", f"Invoiced quantity exceeds accepted receipt quantity on PO line {po_line.line_no}."))
            if invoice.matching_mode == "THREE_WAY" and received_by_line.get(po_line.id, 0) == 0:
                findings.append(("MISSING_RECEIPT", f"No goods receipt exists for PO line {po_line.line_no}."))
        po_total = sum(extended_paise(l.unit_price_paise, Decimal(l.quantity_milli) / 1000) for l in po.lines)
        previously_invoiced = db.query(func.coalesce(func.sum(models.Invoice.subtotal_paise), 0)).filter(models.Invoice.purchase_order_id == po.id, models.Invoice.id != invoice.id, models.Invoice.status != "REJECTED").scalar() or 0
        if invoice.subtotal_paise + previously_invoiced > po_total:
            findings.append(("PO_AMOUNT_VARIANCE", "Cumulative invoice subtotal exceeds the purchase order subtotal."))
    expected_tax = sum(tax_paise(line.subtotal_paise, line.tax_rate_bps) for line in invoice.lines)
    if invoice.tax_paise != expected_tax:
        findings.append(("TAX_VARIANCE", "Invoice tax does not agree with the configured line tax rates."))
    return findings


def store_invoice_lines(invoice: models.Invoice, line_inputs):
    subtotal = 0
    tax_total = 0
    for idx, value in enumerate(line_inputs):
        qty_milli = quantity_milli(value.quantity)
        line_sub = extended_paise(value.unit_price_paise, value.quantity)
        line_tax = tax_paise(line_sub, value.tax_rate_bps)
        subtotal += line_sub
        tax_total += line_tax
        invoice.lines.append(models.InvoiceLine(
            purchase_order_line_id=value.purchase_order_line_id,
            description=value.description, quantity_milli=qty_milli,
            unit_price_paise=value.unit_price_paise, tax_rate_bps=value.tax_rate_bps,
            subtotal_paise=line_sub, tax_paise=line_tax,
        ))
    invoice.subtotal_paise = subtotal
    invoice.tax_paise = tax_total
    invoice.total_paise = subtotal + tax_total


def refresh_invoice_match(db: Session, invoice: models.Invoice):
    findings = match_invoice(db, invoice)
    invoice_findings = db.query(models.ExceptionRecord).filter_by(invoice_id=invoice.id, status="OPEN").all()
    open_categories = {e.category for e in invoice_findings}
    current_categories = {category for category, _ in findings}
    for existing in invoice_findings:
        if existing.category not in current_categories:
            existing.status = "RESOLVED"
            existing.resolution = "Automatically cleared after invoice correction and re-match."
            existing.resolved_at = models.utc_now()
    for category, description in findings:
        if category not in open_categories:
            db.add(models.ExceptionRecord(invoice_id=invoice.id, category=category, description=description))
    if findings:
        invoice.match_outcome = "EXCEPTION"
        if invoice.status not in {"REJECTED", "PAID", "PARTIALLY_PAID"}:
            invoice.status = "EXCEPTION"
    elif invoice.match_outcome != "APPROVED":
        invoice.match_outcome = "MATCHED"
        if invoice.status not in {"REJECTED", "PAID", "PARTIALLY_PAID"}:
            invoice.status = "PENDING_APPROVAL"
    return findings


def update_payment_state(db: Session, invoice: models.Invoice):
    paid = matched_paid(db, invoice)
    if paid > invoice.total_paise:
        raise ValueError("Total payments cannot exceed the approved invoice balance")
    if paid == invoice.total_paise:
        invoice.status = "PAID"
    elif paid > 0:
        invoice.status = "PARTIALLY_PAID"
    return paid
