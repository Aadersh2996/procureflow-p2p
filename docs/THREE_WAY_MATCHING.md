# Invoice matching and financial rules

## Monetary and quantity precision

- INR is represented as integer paise in storage and JSON.
- Quantity is represented as integer milliunits (three decimal places).
- Unit price is integer paise per unit.
- GST is an integer basis-point rate (for example, 1,800 bps = 18%).
- Each line's extension and GST amount are rounded to the nearest paise using decimal `ROUND_HALF_UP`. Invoice totals sum the rounded line values.

## Two-way match

Compares invoice lines with a linked supplier purchase order. It checks the supplier relationship, PO line reference, unit price, cumulative invoiced quantity versus ordered quantity, and cumulative invoice subtotal versus PO subtotal. It does not require a receipt.

## Three-way match

Applies two-way checks and also compares cumulative invoiced quantities against accepted quantities on accepted goods receipts. Received, accepted, and rejected quantities remain separate. A receipt alone is not enough if the accepted quantity is lower.

## Exceptions and approval

The matcher creates exception records for duplicate supplier invoice numbers, missing or inconsistent PO links, unit price variance, cumulative quantity variance, missing receipts, PO amount overrun, and GST arithmetic variance. An AP user can correct an unapproved invoice's source values and rerun matching. A stale exception is then resolved with a system-recorded correction note. Manually resolving an exception does not approve an invoice: the invoice must pass a fresh match and have no open exceptions before approval.

## Payments and reconciliation

Only approved invoices can receive payments. New payment amount must fit within the invoice's remaining balance. Partial payments update the invoice to partially paid; the invoice becomes paid when cumulative payment rows equal its total. Reconciliation recomputes those sums from stored payments rather than relying only on a manually maintained balance.

There is no configurable tolerance policy in this simulation: unit price and quantity comparisons are exact. Tax rates are applied to invoice lines, not to a separately modelled tax jurisdiction or tax code master.
