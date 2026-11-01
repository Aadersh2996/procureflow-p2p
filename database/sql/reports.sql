-- ProcureFlow P2P reports. All currency columns are integer paise.

-- 1. Duplicate supplier invoices. The supplier + invoice-number constraint prevents new duplicates;
-- this query is retained for validating any legacy data imported before that constraint existed.
SELECT supplier_id, UPPER(number) AS invoice_number, COUNT(*) AS copies
FROM invoices GROUP BY supplier_id, UPPER(number) HAVING COUNT(*) > 1;

-- 2. Unmatched invoices that require source-document linkage or investigation.
SELECT i.id, i.number, s.name AS supplier, i.total_paise, i.match_outcome
FROM invoices i JOIN suppliers s ON s.id = i.supplier_id
WHERE i.match_outcome IN ('UNMATCHED', 'EXCEPTION');

-- 3. Price variance exceptions identified during invoice matching.
SELECT i.number, s.name AS supplier, e.description, e.status
FROM exceptions e JOIN invoices i ON i.id = e.invoice_id JOIN suppliers s ON s.id = i.supplier_id
WHERE e.category = 'PRICE_VARIANCE';

-- 4. Quantity variance exceptions (ordered or accepted receipt quantity exceeded).
SELECT i.number, e.category, e.description
FROM exceptions e JOIN invoices i ON i.id = e.invoice_id
WHERE e.category IN ('PO_QUANTITY_VARIANCE', 'RECEIPT_QUANTITY_VARIANCE');

-- 5. Cumulative invoice subtotals exceeding purchase order subtotals.
WITH po_totals AS (
  SELECT purchase_order_id, SUM((unit_price_paise * quantity_milli + 500) / 1000) AS po_subtotal_paise
  FROM purchase_order_lines GROUP BY purchase_order_id
), invoice_totals AS (
  SELECT purchase_order_id, SUM(subtotal_paise) AS invoiced_paise
  FROM invoices WHERE purchase_order_id IS NOT NULL AND status <> 'REJECTED' GROUP BY purchase_order_id
)
SELECT p.number AS po_number, s.name AS supplier, it.invoiced_paise, pt.po_subtotal_paise
FROM invoice_totals it JOIN purchase_orders p ON p.id = it.purchase_order_id
JOIN suppliers s ON s.id = p.supplier_id JOIN po_totals pt ON pt.purchase_order_id = p.id
WHERE it.invoiced_paise > pt.po_subtotal_paise;

-- 6. Invoice quantities exceeding accepted goods receipt quantities for any PO line.
WITH received AS (
  SELECT purchase_order_line_id, SUM(accepted_quantity_milli) AS accepted_milli
  FROM goods_receipt_lines GROUP BY purchase_order_line_id
), billed AS (
  SELECT il.purchase_order_line_id, SUM(il.quantity_milli) AS invoiced_milli
  FROM invoice_lines il JOIN invoices i ON i.id = il.invoice_id
  WHERE i.status <> 'REJECTED' AND il.purchase_order_line_id IS NOT NULL
  GROUP BY il.purchase_order_line_id
)
SELECT pol.purchase_order_id, pol.line_no, pol.description, billed.invoiced_milli, COALESCE(received.accepted_milli, 0) AS accepted_milli
FROM billed JOIN purchase_order_lines pol ON pol.id = billed.purchase_order_line_id
LEFT JOIN received ON received.purchase_order_line_id = pol.id
WHERE billed.invoiced_milli > COALESCE(received.accepted_milli, 0);

-- 7. Purchase orders without a goods receipt.
SELECT p.number, s.name AS supplier, p.ordered_on, p.status
FROM purchase_orders p JOIN suppliers s ON s.id = p.supplier_id
LEFT JOIN goods_receipts g ON g.purchase_order_id = p.id
WHERE g.id IS NULL AND p.status NOT IN ('CANCELLED', 'DRAFT');

-- 8. Purchase orders with a partial cumulative receipt.
WITH received AS (
  SELECT p.id AS po_id, SUM(grl.received_quantity_milli) AS received_milli
  FROM purchase_orders p JOIN purchase_order_lines pol ON pol.purchase_order_id = p.id
  JOIN goods_receipt_lines grl ON grl.purchase_order_line_id = pol.id GROUP BY p.id
), ordered AS (
  SELECT purchase_order_id AS po_id, SUM(quantity_milli) AS ordered_milli FROM purchase_order_lines GROUP BY purchase_order_id
)
SELECT p.number, s.name AS supplier, received.received_milli, ordered.ordered_milli
FROM received JOIN ordered ON ordered.po_id = received.po_id JOIN purchase_orders p ON p.id = received.po_id
JOIN suppliers s ON s.id = p.supplier_id WHERE received.received_milli < ordered.ordered_milli;

-- 9. Invoices pending approval, together with their latest matching result.
SELECT i.number, s.name AS supplier, i.total_paise, i.due_date, i.match_outcome
FROM invoices i JOIN suppliers s ON s.id = i.supplier_id WHERE i.status = 'PENDING_APPROVAL';

-- 10. Overdue invoices with a positive open balance.
WITH paid AS (SELECT invoice_id, SUM(amount_paise) AS paid_paise FROM payments GROUP BY invoice_id)
SELECT i.number, s.name AS supplier, i.due_date, i.total_paise - COALESCE(paid.paid_paise, 0) AS outstanding_paise
FROM invoices i JOIN suppliers s ON s.id = i.supplier_id LEFT JOIN paid ON paid.invoice_id = i.id
WHERE i.due_date < date('now') AND i.status IN ('APPROVED', 'PARTIALLY_PAID')
  AND i.total_paise > COALESCE(paid.paid_paise, 0);

-- 11. Supplier-wise expenditure from persisted invoices.
SELECT s.code, s.name, SUM(i.total_paise) AS invoiced_paise
FROM invoices i JOIN suppliers s ON s.id = i.supplier_id
WHERE i.status <> 'REJECTED' GROUP BY s.id, s.code, s.name ORDER BY invoiced_paise DESC;

-- 12. Monthly invoice expenditure (invoice date, not payment date).
SELECT strftime('%Y-%m', invoice_date) AS month, SUM(total_paise) AS invoiced_paise
FROM invoices WHERE status <> 'REJECTED' GROUP BY strftime('%Y-%m', invoice_date) ORDER BY month;

-- 13. Outstanding balances for approved or partially paid invoices.
WITH paid AS (SELECT invoice_id, SUM(amount_paise) AS paid_paise FROM payments GROUP BY invoice_id)
SELECT i.number, s.name AS supplier, i.total_paise, COALESCE(paid.paid_paise, 0) AS paid_paise,
       i.total_paise - COALESCE(paid.paid_paise, 0) AS outstanding_paise
FROM invoices i JOIN suppliers s ON s.id = i.supplier_id LEFT JOIN paid ON paid.invoice_id = i.id
WHERE i.status IN ('APPROVED', 'PARTIALLY_PAID') AND i.total_paise > COALESCE(paid.paid_paise, 0);

-- 14. Partial payments: an invoice has payments but is not fully settled.
WITH paid AS (SELECT invoice_id, SUM(amount_paise) AS paid_paise FROM payments GROUP BY invoice_id)
SELECT i.number, s.name AS supplier, paid.paid_paise, i.total_paise - paid.paid_paise AS remaining_paise
FROM invoices i JOIN suppliers s ON s.id = i.supplier_id JOIN paid ON paid.invoice_id = i.id
WHERE paid.paid_paise > 0 AND paid.paid_paise < i.total_paise;

-- 15. Fully settled invoices, reconciled to their payment ledger total.
SELECT i.number, s.name AS supplier, i.total_paise, SUM(p.amount_paise) AS paid_paise
FROM invoices i JOIN suppliers s ON s.id = i.supplier_id JOIN payments p ON p.invoice_id = i.id
GROUP BY i.id, i.number, s.name, i.total_paise HAVING SUM(p.amount_paise) = i.total_paise;

-- 16. Matching outcomes to highlight exceptions and unmatched transactions.
SELECT match_outcome, COUNT(*) AS invoice_count, SUM(total_paise) AS invoice_paise
FROM invoices GROUP BY match_outcome ORDER BY invoice_count DESC;
