# ProcureFlow demonstration walkthrough

## Deliverables

- `ProcureFlow_Demo.mp4` — silent H.264 video, 1600 × 900, 25 fps, approximately 3 minutes 27 seconds.

## Walkthrough

| Approx. time | Section | What is shown |
| --- | --- | --- |
| 00:00–00:21 | Overview | Dashboard metrics, spend trend, operational attention items, and recent invoices. |
| 00:21–00:39 | Suppliers | Supplier search and the Aarav Office Systems profile. |
| 00:39–01:01 | Requisition and order | A submitted requisition and its related purchase order. |
| 01:01–01:16 | Receiving | Goods receipt and accepted quantities. |
| 01:16–01:32 | Invoices | Invoice register and matched invoice detail for `INV-DEMO-006`. |
| 01:32–02:00 | Three-way match | Related purchase order, accepted receipt, and invoice records. |
| 02:00–02:21 | Exception handling | Open price variance for `INV-DEMO-005`; the exception remains open. |
| 02:21–02:43 | Payment | Recording a ₹12,980 NEFT payment against `INV-DEMO-002`. |
| 02:43–03:14 | Reconciliation and reports | The settled invoice balance and live reporting views. |
| 03:14–03:27 | Close | Return to the procurement overview. |

## Recording and data notes

The browser recording used the running ProcureFlow application against an isolated SQLite copy at `artifacts/demo/recording.sqlite`. That local copy was reset and seeded with fictional INR demonstration records before the successful take. It contained 10 suppliers, 10 requisitions, 10 purchase orders, 8 goods receipts, and 24 invoices. The recording copy is intentionally excluded from the public repository, and no recording transaction was written to the original database.

The video records payment reference `PAY-261101-0004`, settling the remaining ₹12,980 balance on the ₹25,960 invoice `INV-DEMO-002`. The `INV-DEMO-005` price variance is shown as open and is not resolved. No invoice approval is performed in the video.

The video is silent, with no narration or music. Chromium browser diagnostics recorded no console errors or failed requests in the successful take. The current app exposes operational reports and CSV exports; it has no interactive SQL reporting interface to demonstrate.

The original local app services were restarted and verified after recording.
