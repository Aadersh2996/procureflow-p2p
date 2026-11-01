# Procure-to-pay process flow

```mermaid
flowchart LR
  A[Department need] --> B[Requisition submitted]
  B --> C{Department approval}
  C -- Reject --> B
  C -- Approve --> D[Supplier and purchase order]
  D --> E{PO approval and release}
  E -- Reject --> D
  E -- Release --> F[Goods receipt]
  F --> G[Accepted / rejected quantities]
  G --> H[Supplier invoice]
  H --> I{Two-way or three-way match}
  I -- Exception --> J[Investigate and correct source data]
  J --> I
  I -- Clean --> K[Finance approval]
  K -- Reject --> L[Rejected invoice]
  K -- Approve --> M[Payment(s)]
  M --> N[Reconciliation]
```

```mermaid
erDiagram
  SUPPLIERS ||--o{ PURCHASE_ORDERS : supplies
  REQUISITIONS ||--o{ PURCHASE_ORDERS : sources
  PURCHASE_ORDERS ||--|{ PURCHASE_ORDER_LINES : contains
  PURCHASE_ORDERS ||--o{ GOODS_RECEIPTS : receives
  PURCHASE_ORDER_LINES ||--o{ GOODS_RECEIPT_LINES : accepted_against
  SUPPLIERS ||--o{ INVOICES : bills
  PURCHASE_ORDERS o|--o{ INVOICES : matched_to
  INVOICES ||--|{ INVOICE_LINES : contains
  INVOICES ||--o{ EXCEPTIONS : flags
  INVOICES ||--o{ PAYMENTS : settled_by
```
