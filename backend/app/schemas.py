from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SupplierCreate(BaseModel):
    code: str = Field(min_length=2, max_length=24)
    name: str = Field(min_length=2, max_length=180)
    contact_person: str = ""
    email: EmailStr
    phone: str = ""
    address: str = ""
    gstin: str | None = Field(default=None, max_length=15)
    pan: str | None = Field(default=None, max_length=10)
    payment_terms_days: int = Field(default=30, ge=0, le=180)

    @field_validator("gstin", "pan", mode="before")
    @classmethod
    def normalize_optional_tax_id(cls, value):
        if value == "":
            return None
        return value

    @field_validator("gstin")
    @classmethod
    def validate_gstin_length(cls, value):
        if value is not None and len(value) != 15:
            raise ValueError("GSTIN must be 15 characters")
        return value

    @field_validator("pan")
    @classmethod
    def validate_pan_length(cls, value):
        if value is not None and len(value) != 10:
            raise ValueError("PAN must be 10 characters")
        return value


class LoginInput(BaseModel):
    username: str = Field(min_length=2, max_length=48)
    password: str = Field(min_length=1, max_length=128)


class SupplierUpdate(BaseModel):
    name: str | None = None
    contact_person: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    gstin: str | None = None
    pan: str | None = None
    payment_terms_days: int | None = Field(default=None, ge=0, le=180)
    active: bool | None = None

    @field_validator("gstin", "pan", mode="before")
    @classmethod
    def normalize_optional_tax_id(cls, value):
        return None if value == "" else value


class LineInput(BaseModel):
    description: str = Field(min_length=2, max_length=200)
    quantity: Decimal = Field(gt=0, multiple_of=Decimal("0.001"))
    unit_price_paise: int = Field(gt=0)
    tax_rate_bps: int = Field(default=1800, ge=0, le=2800)
    purchase_order_line_id: int | None = None


class RequisitionCreate(BaseModel):
    requester: str = Field(min_length=2)
    department: str = Field(min_length=2)
    description: str = Field(min_length=2)
    lines: list[LineInput] = Field(min_length=1)


class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    requisition_id: int | None = None
    expected_on: date | None = None
    lines: list[LineInput] = Field(min_length=1)


class ReceiptLineInput(BaseModel):
    purchase_order_line_id: int
    received_quantity: Decimal = Field(gt=0, multiple_of=Decimal("0.001"))
    accepted_quantity: Decimal = Field(ge=0, multiple_of=Decimal("0.001"))


class ReceiptCreate(BaseModel):
    purchase_order_id: int
    received_by: str = Field(min_length=2)
    received_on: date = Field(default_factory=date.today)
    lines: list[ReceiptLineInput] = Field(min_length=1)


class InvoiceCreate(BaseModel):
    number: str = Field(min_length=2, max_length=48)
    supplier_id: int
    purchase_order_id: int | None = None
    invoice_date: date
    due_date: date
    matching_mode: str = Field(default="THREE_WAY", pattern="^(TWO_WAY|THREE_WAY)$")
    reported_tax_paise: int | None = Field(default=None, ge=0)
    lines: list[LineInput] = Field(min_length=1)


class InvoiceUpdate(BaseModel):
    purchase_order_id: int | None = None
    matching_mode: str | None = Field(default=None, pattern="^(TWO_WAY|THREE_WAY)$")
    invoice_date: date | None = None
    due_date: date | None = None
    reported_tax_paise: int | None = Field(default=None, ge=0)
    lines: list[LineInput] | None = None


class DecisionInput(BaseModel):
    actor: str | None = None  # accepted for older demo clients; audit identity comes from the signed-in account
    decision: str = Field(pattern="^(APPROVED|REJECTED)$")
    comment: str = ""


class PaymentCreate(BaseModel):
    invoice_id: int
    amount_paise: int = Field(gt=0)
    paid_on: date = Field(default_factory=date.today)
    method: str = "NEFT"
    note: str = ""


class ResolveInput(BaseModel):
    resolution: str = Field(min_length=3)
