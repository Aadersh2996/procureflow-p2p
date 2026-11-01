# SQL reports

Executable SQLite queries are in [`database/sql/reports.sql`](../database/sql/reports.sql). They use the application's current table and column names and integer-paise currency values.

The report set covers duplicate invoices, unmatched invoices, price and quantity variances, cumulative invoices above PO value, invoices above accepted receipts, POs without receipts, partial receipts, pending approvals, overdue invoices, supplier and monthly expenditure, outstanding and partial payments, settled invoices, and matching outcomes.

Run against the project database from PowerShell:

```powershell
sqlite3 .\p2p.db ".read .\database\sql\reports.sql"
```

Install the SQLite command-line utility separately if `sqlite3` is not available. The app itself does not require it; Python's SQLite support is included with standard Python builds.
