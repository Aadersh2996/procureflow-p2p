from datetime import date, timedelta
from decimal import Decimal

from app import models
from app.core.database import Base, SessionLocal, engine
from app.services import audit, extended_paise, refresh_invoice_match, store_invoice_lines, update_payment_state
from app.api import password_hash

SUPPLIERS = [
    ("SUP-1001", "Aarav Office Systems", "Neha Iyer", "neha@aaravoffice.example", "29AABCA1001A1Z5"),
    ("SUP-1002", "BluePeak Industrial Supplies", "Rohan Mehta", "rohan@bluepeak.example", "27AABCB1002B1Z6"),
    ("SUP-1003", "Cedar IT Services", "Priya Shah", "priya@cedarit.example", "24AABCC1003C1Z7"),
    ("SUP-1004", "Dhanush Safety Products", "Arjun Rao", "arjun@dhanushsafety.example", "29AABCD1004D1Z8"),
    ("SUP-1005", "Eastline Packaging Co.", "Kavya Das", "kavya@eastline.example", "19AABCE1005E1Z9"),
    ("SUP-1006", "Fable Facilities India", "Aditi Nair", "aditi@fablefacilities.example", "32AABCF1006F1Z2"),
    ("SUP-1007", "Greenway Electricals", "Vikram Joshi", "vikram@greenway.example", "27AABCG1007G1Z3"),
    ("SUP-1008", "Harbor Network Hardware", "Ishita Sen", "ishita@harborhardware.example", "07AABCH1008H1Z4"),
    ("SUP-1009", "Indus Lab Equipment", "Dev Malhotra", "dev@induslab.example", "06AABCI1009I1Z5"),
    ("SUP-1010", "Juniper Learning Resources", "Mira Kapoor", "mira@juniperlearn.example", "09AABCJ1010J1Z6"),
]


def seed_demo(reset=False):
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if reset:
            for table in reversed(Base.metadata.sorted_tables):
                db.execute(table.delete())
            db.commit()
        if db.query(models.Supplier).count():
            return {"seeded": False, "reason": "Demo records already exist; use reset=True to replace them."}
        suppliers = []
        for code, name, contact, email, gstin in SUPPLIERS:
            item = models.Supplier(code=code, name=name, contact_person=contact, email=email, phone="+91 80 4000 1000",
                address="Bengaluru, Karnataka, India", gstin=gstin, pan="AABCA1234A", payment_terms_days=30, fictional=True)
            db.add(item); suppliers.append(item)
        for role in ["admin", "requester", "procurement", "receiving", "ap", "approver", "viewer"]:
            db.add(models.UserAccount(username=role, role=role, password_hash=password_hash(f"demo-{role}")))
        db.flush()
        today = date.today()
        orders = []
        requisitions = []
        for i, supplier in enumerate(suppliers):
            req = models.Requisition(number=f"REQ-DEMO-{i+1:03d}", requester=["Ananya Rao", "Kabir Shah", "Meera Nair"][i % 3],
                department=["Finance", "Operations", "Information Technology", "Facilities"][i % 4],
                description=f"Quarterly operating supplies request {i+1}", status="APPROVED")
            req.lines.append(models.RequisitionLine(description=f"Business supplies batch {i+1}", quantity_milli=10000, estimated_unit_price_paise=1000000+i*100000))
            db.add(req); requisitions.append(req)
            po = models.PurchaseOrder(number=f"PO-DEMO-{i+1:03d}", supplier=supplier, requisition=req,
                ordered_on=today-timedelta(days=45-i), expected_on=today-timedelta(days=10), status="OPEN")
            po.lines.append(models.PurchaseOrderLine(line_no=1, description=f"Business supplies batch {i+1}", quantity_milli=10000,
                unit_price_paise=1000000+i*100000, tax_rate_bps=1800))
            db.add(po); orders.append(po)
        db.flush()
        # Full, partial, and missing receipts, all within PO quantities.
        for idx in range(8):
            qty = 10000 if idx not in (3, 6) else 5000
            rec = models.GoodsReceipt(number=f"GRN-DEMO-{idx+1:03d}", purchase_order_id=orders[idx].id,
                received_on=today-timedelta(days=30-idx), received_by="Receiving Team", status="ACCEPTED")
            rec.lines.append(models.GoodsReceiptLine(purchase_order_line_id=orders[idx].lines[0].id, received_quantity_milli=qty,
                accepted_quantity_milli=qty-(1000 if idx == 4 else 0), rejected_quantity_milli=1000 if idx == 4 else 0))
            db.add(rec)
            orders[idx].status = "RECEIVED" if qty == 10000 else "PARTIALLY_RECEIVED"
        db.flush()
        invoices = []
        # Twenty four invoices cover clean matching, multiple invoices, cumulative receipt limits, and exceptions.
        for idx in range(24):
            po_idx = idx % 10
            po = orders[po_idx]
            po_line = po.lines[0]
            qty = Decimal("2.000")
            price = po_line.unit_price_paise
            po_link = po.id
            line_po_link = po_line.id
            if idx == 4:  # price variance
                price += 12500
            if idx == 5:  # quantity variance beyond accepted receipt
                qty = Decimal("8.000")
            if idx == 6:  # missing receipt
                qty = Decimal("1.000")
            if idx == 7:  # missing PO
                po_link = None; line_po_link = None
            if idx == 8:  # tax variance in received source document
                pass
            number = f"INV-DEMO-{idx+1:03d}"
            inv_date = today-timedelta(days=40-idx)
            inv = models.Invoice(number=number, supplier_id=po.supplier_id, purchase_order_id=po_link,
                invoice_date=inv_date, due_date=inv_date+timedelta(days=30))
            from app.schemas import LineInput
            line = LineInput(description=po_line.description, quantity=qty, unit_price_paise=price, tax_rate_bps=po_line.tax_rate_bps,
                purchase_order_line_id=line_po_link)
            store_invoice_lines(inv, [line])
            if idx == 8:
                inv.tax_paise += 2750; inv.total_paise += 2750
            db.add(inv); db.flush(); invoices.append(inv)
        db.flush()
        for idx, inv in enumerate(invoices):
            findings = refresh_invoice_match(db, inv)
            if idx in (0, 1, 2, 9, 10, 11, 12, 13, 14, 15, 16, 17):
                # Seed approved clean cases only. Invoices 0..2 are deliberately on fully received PO 1/2/3.
                if not findings and inv.status == "PENDING_APPROVAL":
                    inv.status = "APPROVED"; inv.match_outcome = "APPROVED"
                    db.add(models.Approval(entity_type="INVOICE", entity_id=inv.id, approver="Finance Approver", decision="APPROVED", comment="Matched and approved"))
            if idx == 18:
                inv.status = "REJECTED"
                db.add(models.Approval(entity_type="INVOICE", entity_id=inv.id, approver="Finance Approver", decision="REJECTED", comment="Supporting documentation incomplete"))
        # The supplier+invoice-number database constraint blocks duplicates before they are persisted.
        # This audit exception records a blocked duplicate attempt without storing a duplicate financial document.
        db.add(models.ExceptionRecord(invoice_id=invoices[3].id, category="DUPLICATE", status="OPEN",
            description="A second submission of INV-DEMO-001 for the same supplier was blocked by duplicate prevention."))
        # Paid and partial payment examples against approved invoices.
        for idx, proportion in ((0, 1.0), (1, 0.5), (2, 1.0)):
            inv = invoices[idx]
            if inv.status != "APPROVED":
                continue
            amount = inv.total_paise if proportion == 1.0 else inv.total_paise // 2
            db.add(models.Payment(reference=f"PAY-DEMO-{idx+1:03d}", invoice_id=inv.id, paid_on=today-timedelta(days=2),
                amount_paise=amount, method="NEFT", note="Demonstration payment"))
            db.flush(); update_payment_state(db, inv)
        for item in requisitions:
            db.add(models.Approval(entity_type="REQUISITION", entity_id=item.id, approver="Department Approver", decision="APPROVED", comment="Within budget"))
            audit(db, "requisition", item.id, "APPROVED", "Demonstration approval", "Department Approver")
        for po in orders:
            db.add(models.Approval(entity_type="PURCHASE_ORDER", entity_id=po.id, approver="Procurement Approver", decision="APPROVED", comment="Supplier and budget validated"))
            audit(db, "purchase_order", po.id, "APPROVED", "Demonstration order release", "Procurement Approver")
        for inv in invoices:
            audit(db, "invoice", inv.id, "SEEDED", f"Fictional demonstration invoice {inv.number}")
        db.commit()
        return {"seeded": True, "suppliers": 10, "requisitions": 10, "purchase_orders": 10, "goods_receipts": 8, "invoices": 24, "blocked_duplicate_attempt_recorded": True}
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Seed fictional ProcureFlow demo data.")
    parser.add_argument("--reset", action="store_true", help="Clear the local project database and recreate the fictional demo set.")
    args = parser.parse_args()
    print(seed_demo(reset=args.reset))
