# Database design

The application uses SQLite for local development. Integer identifiers are primary keys; declared foreign keys use restrictive deletion behavior for financial records, and foreign-key columns used for joins are indexed. Invoice number uniqueness is scoped to a supplier. Currency is stored as integer paise, quantities as integer thousandths, and tax rates as integer basis points.

| Table | Purpose |
|---|---|
| `user_accounts` | Local demo username, password hash, role, and active state |
| `suppliers` | Supplier identity, contact, India tax IDs, payment terms, and active flag |
| `requisitions`, `requisition_lines` | Requesting department, business purpose, and requested lines |
| `purchase_orders`, `purchase_order_lines` | Supplier commitment, source request, ordered quantity, price, and tax rate |
| `goods_receipts`, `goods_receipt_lines` | Receipt headers and delivered/accepted/rejected quantities by PO line |
| `invoices`, `invoice_lines` | Supplier invoice source data, match outcome, workflow, tax, and calculated totals |
| `exceptions` | Mismatch category, description, resolution, and timestamps |
| `approvals` | Requisition, PO, and invoice approval decisions |
| `payments` | Payment reference, invoice, date, amount, method, and note |
| `audit_events` | Append-oriented business action trail for changed records |

```mermaid
erDiagram
  SUPPLIERS { int id PK string code UK string name string email UK string gstin UK int payment_terms_days bool active }
  USER_ACCOUNTS { int id PK string username UK string password_hash string role bool active }
  REQUISITIONS { int id PK string number UK string requester string department string status }
  REQUISITION_LINES { int id PK int requisition_id FK int quantity_milli int estimated_unit_price_paise }
  PURCHASE_ORDERS { int id PK string number UK int supplier_id FK int requisition_id FK string status }
  PURCHASE_ORDER_LINES { int id PK int purchase_order_id FK int line_no int quantity_milli int unit_price_paise int tax_rate_bps }
  GOODS_RECEIPTS { int id PK string number UK int purchase_order_id FK date received_on string status }
  GOODS_RECEIPT_LINES { int id PK int goods_receipt_id FK int purchase_order_line_id FK int received_quantity_milli int accepted_quantity_milli }
  INVOICES { int id PK string number int supplier_id FK int purchase_order_id FK int subtotal_paise int tax_paise int total_paise string status }
  INVOICE_LINES { int id PK int invoice_id FK int purchase_order_line_id FK int quantity_milli int unit_price_paise int tax_paise }
  EXCEPTIONS { int id PK int invoice_id FK string category string status string resolution }
  APPROVALS { int id PK string entity_type int entity_id string approver string decision }
  PAYMENTS { int id PK string reference UK int invoice_id FK int amount_paise date paid_on }
  AUDIT_EVENTS { int id PK string entity_type int entity_id string action string actor datetime occurred_at }
  SUPPLIERS ||--o{ PURCHASE_ORDERS : supplier_id
  SUPPLIERS ||--o{ INVOICES : supplier_id
  REQUISITIONS ||--o{ REQUISITION_LINES : requisition_id
  REQUISITIONS ||--o{ PURCHASE_ORDERS : requisition_id
  PURCHASE_ORDERS ||--|{ PURCHASE_ORDER_LINES : purchase_order_id
  PURCHASE_ORDERS ||--o{ GOODS_RECEIPTS : purchase_order_id
  GOODS_RECEIPTS ||--|{ GOODS_RECEIPT_LINES : goods_receipt_id
  PURCHASE_ORDER_LINES ||--o{ GOODS_RECEIPT_LINES : purchase_order_line_id
  PURCHASE_ORDERS o|--o{ INVOICES : purchase_order_id
  INVOICES ||--|{ INVOICE_LINES : invoice_id
  INVOICES ||--o{ EXCEPTIONS : invoice_id
  INVOICES ||--o{ PAYMENTS : invoice_id
```

## Migration and database initialization

Alembic migrations live under `backend/migrations`. The initial migration creates the SQLAlchemy metadata. `Base.metadata.create_all()` in the FastAPI lifespan keeps a fresh local checkout runnable; subsequent structural changes should be added as forward Alembic revisions.
