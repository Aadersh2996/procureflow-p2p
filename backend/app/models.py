from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    contact_person: Mapped[str] = mapped_column(String(120), default="")
    email: Mapped[str] = mapped_column(String(180), unique=True)
    phone: Mapped[str] = mapped_column(String(40), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    gstin: Mapped[str | None] = mapped_column(String(15), unique=True, nullable=True)
    pan: Mapped[str | None] = mapped_column(String(10), nullable=True)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=30)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    fictional: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class UserAccount(Base):
    __tablename__ = "user_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(24), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Requisition(Base):
    __tablename__ = "requisitions"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    requester: Mapped[str] = mapped_column(String(120))
    department: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="DRAFT", index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    lines: Mapped[list["RequisitionLine"]] = relationship(back_populates="requisition", cascade="all, delete-orphan")


class RequisitionLine(Base):
    __tablename__ = "requisition_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    requisition_id: Mapped[int] = mapped_column(ForeignKey("requisitions.id", ondelete="CASCADE"), index=True)
    description: Mapped[str] = mapped_column(String(200))
    quantity_milli: Mapped[int] = mapped_column(Integer)
    estimated_unit_price_paise: Mapped[int] = mapped_column(Integer)
    requisition: Mapped[Requisition] = relationship(back_populates="lines")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True)
    requisition_id: Mapped[int | None] = mapped_column(ForeignKey("requisitions.id", ondelete="RESTRICT"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="DRAFT", index=True)
    ordered_on: Mapped[date] = mapped_column(Date, default=date.today)
    expected_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    supplier: Mapped[Supplier] = relationship()
    requisition: Mapped[Requisition | None] = relationship()
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(back_populates="purchase_order", cascade="all, delete-orphan")


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True)
    line_no: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(200))
    quantity_milli: Mapped[int] = mapped_column(Integer)
    unit_price_paise: Mapped[int] = mapped_column(Integer)
    tax_rate_bps: Mapped[int] = mapped_column(Integer, default=1800)
    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="lines")
    __table_args__ = (UniqueConstraint("purchase_order_id", "line_no"),)


class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id", ondelete="RESTRICT"), index=True)
    received_on: Mapped[date] = mapped_column(Date, default=date.today)
    received_by: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(24), default="ACCEPTED", index=True)
    lines: Mapped[list["GoodsReceiptLine"]] = relationship(back_populates="receipt", cascade="all, delete-orphan")


class GoodsReceiptLine(Base):
    __tablename__ = "goods_receipt_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    goods_receipt_id: Mapped[int] = mapped_column(ForeignKey("goods_receipts.id", ondelete="CASCADE"), index=True)
    purchase_order_line_id: Mapped[int] = mapped_column(ForeignKey("purchase_order_lines.id", ondelete="RESTRICT"), index=True)
    received_quantity_milli: Mapped[int] = mapped_column(Integer)
    accepted_quantity_milli: Mapped[int] = mapped_column(Integer)
    rejected_quantity_milli: Mapped[int] = mapped_column(Integer, default=0)
    receipt: Mapped[GoodsReceipt] = relationship(back_populates="lines")


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(48), index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True)
    purchase_order_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id", ondelete="RESTRICT"), nullable=True, index=True)
    invoice_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(24), default="RECEIVED", index=True)
    match_outcome: Mapped[str] = mapped_column(String(24), default="UNMATCHED", index=True)
    matching_mode: Mapped[str] = mapped_column(String(16), default="THREE_WAY")
    subtotal_paise: Mapped[int] = mapped_column(Integer, default=0)
    tax_paise: Mapped[int] = mapped_column(Integer, default=0)
    total_paise: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    supplier: Mapped[Supplier] = relationship()
    lines: Mapped[list["InvoiceLine"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("supplier_id", "number", name="uq_invoice_supplier_number"),)


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    purchase_order_line_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_order_lines.id", ondelete="RESTRICT"), nullable=True, index=True)
    description: Mapped[str] = mapped_column(String(200))
    quantity_milli: Mapped[int] = mapped_column(Integer)
    unit_price_paise: Mapped[int] = mapped_column(Integer)
    tax_rate_bps: Mapped[int] = mapped_column(Integer, default=1800)
    subtotal_paise: Mapped[int] = mapped_column(Integer)
    tax_paise: Mapped[int] = mapped_column(Integer)
    invoice: Mapped[Invoice] = relationship(back_populates="lines")


class ExceptionRecord(Base):
    __tablename__ = "exceptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="RESTRICT"), index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="OPEN", index=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(24), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    approver: Mapped[str] = mapped_column(String(120))
    decision: Mapped[str] = mapped_column(String(24), index=True)
    comment: Mapped[str] = mapped_column(Text, default="")
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="RESTRICT"), index=True)
    paid_on: Mapped[date] = mapped_column(Date, default=date.today)
    amount_paise: Mapped[int] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(24), default="NEFT")
    note: Mapped[str] = mapped_column(Text, default="")
    invoice: Mapped[Invoice] = relationship()


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(24), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(48))
    actor: Mapped[str] = mapped_column(String(120), default="Demo User")
    detail: Mapped[str] = mapped_column(Text, default="")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
