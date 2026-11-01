# Business test cases

| ID | Scenario | Expected result |
|---|---|---|
| P2P-01 | Register a supplier with a new code and email | Record is saved and audit event is written |
| P2P-02 | Register a repeated supplier code or email | Request is rejected without a second supplier row |
| P2P-03 | Submit a requisition as a requester | Requisition enters Submitted state |
| P2P-04 | Approve a submitted requisition as approver | Approval record and approved state are stored |
| P2P-05 | Attempt to decide an already approved requisition | Invalid transition is rejected |
| P2P-06 | Create PO from an unapproved requisition | API rejects the order |
| P2P-07 | Release a draft PO as approver | PO becomes Open and decision is audited |
| P2P-08 | Record receipt with accepted quantity above received | Receipt is rejected |
| P2P-09 | Record a cumulative receipt above PO quantity | Second receipt is rejected |
| P2P-10 | Record an accepted partial delivery | PO remains partially received; accepted quantity is available for matching |
| P2P-11 | Submit the same supplier invoice number twice | Duplicate is rejected and DB uniqueness protects the record |
| P2P-12 | Match invoice without a PO in three-way mode | Missing PO exception is recorded |
| P2P-13 | Two-way service invoice references a valid PO line without a receipt | Receipt check is skipped, other PO checks still apply |
| P2P-14 | Three-way invoice quantity exceeds accepted receipts | Receipt quantity variance is recorded |
| P2P-15 | Invoice unit price differs from the PO line | Price variance exception is recorded |
| P2P-16 | Invoices cumulatively exceed PO line quantity | Cumulative quantity exception is recorded |
| P2P-17 | Reported GST differs from configured line tax | Tax variance is recorded |
| P2P-18 | Correct source details and rerun match | Stale exception is resolved and invoice returns to Pending Approval if clean |
| P2P-19 | Approver tries to approve invoice with open exceptions | Approval is denied |
| P2P-20 | Viewer attempts an AP payment action | API returns forbidden |
| P2P-21 | Record a payment smaller than the invoice balance | Invoice becomes partially paid |
| P2P-22 | Record final payment equal to remaining balance | Invoice becomes paid |
| P2P-23 | Payment exceeds remaining approved balance | Payment is rejected and no row is added |
| P2P-24 | Reconciliation after a partial payment | Paid and open balances equal invoice total |
| P2P-25 | Import CSV with a valid row and duplicate row | Valid row imports; duplicate row is returned with its row number |
| P2P-26 | Search suppliers by identifier or name | Visible result set narrows without changing stored data |
| P2P-27 | Refresh after a transaction update | Persisted record remains available from the API |
| P2P-28 | Reset the demonstration database and reseed | Seed set is recreated with consistent references |
| P2P-29 | Change selected demo role | Frontend obtains a signed server session for that account |
| P2P-30 | Alter a session token | Protected read or write is rejected with 401 |
