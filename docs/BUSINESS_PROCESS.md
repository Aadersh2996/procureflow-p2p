# Business process

Procure-to-pay connects a department's business need to a supplier obligation and its settlement. Each stage adds evidence that the next stage can validate.

| Stage | Typical owner | Record | Control |
|---|---|---|---|
| Identify need | Requesting department | Requisition and lines | Business purpose, quantity, estimated value, department approval |
| Select supplier | Procurement | Supplier profile and PO | Supplier active, supplier is linked to the request, PO approval |
| Receive | Receiving | Goods receipt note and lines | PO reference, cumulative received quantity, accepted/rejected quantity |
| Validate obligation | Accounts payable | Supplier invoice and lines | Supplier invoice uniqueness, amount/tax calculation, PO and receipt match |
| Approve liability | Finance approver | Approval decision | Clean match and no open exceptions before approval |
| Pay | Accounts payable / treasury | Payment | Approved invoice and balance cap prevent overpayment |
| Reconcile | Accounts payable / finance | Reconciliation report | Invoice value less recorded payment rows equals open balance |

The demonstration separates requester, procurement, receiving, AP, approver, viewer, and administrator roles. The role checks are server-side and backed by signed local session tokens. They demonstrate authorization boundaries; they do not provide enterprise identity management.

All organizations, people, addresses, suppliers, and transactions in the included seed set are fictional.
