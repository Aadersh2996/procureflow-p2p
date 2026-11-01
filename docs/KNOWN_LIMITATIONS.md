# Known limitations

- The system is a local educational workflow simulation. It is not Oracle Fusion, Oracle-certified, or integrated with Oracle, banks, GSTN, email, or external supplier systems.
- Demo users and passwords are intentionally simple and disclosed. If `P2P_SESSION_SECRET` is unset, the API creates a random process-local signing key; sessions are invalidated on restart. Set a private environment value to retain sessions between restarts. There is no MFA, identity provider, password reset, refresh token, or production-grade secret provisioning flow.
- The simulation uses one INR currency, one local SQLite database, integer paise, and fixed quantity precision of three decimal places. It has no multi-currency revaluation, general ledger, accounting period close, or journal posting.
- GST is arithmetic over a line's supplied rate; place-of-supply, intra/inter-state CGST/SGST/IGST selection, HSN/SAC, reverse charge, exemptions, and filing are outside scope.
- Matching is exact and has no configurable tolerance policy, freight/discount allocation, PO amendments, or multiple tax distributions per line.
- Requisition and PO forms create one line per transaction in the current interface. The relational model supports multiple lines, and the API schemas accept line arrays.
- CSV supplier import supports row-level validation; other register exports are provided, but invoice/PO bulk imports and XLSX are not implemented.
- Approval rules are demo roles and simple state checks, not configurable approval matrices, delegation, segregation-of-duties administration, or SSO.
- Audit records demonstrate workflow history but are stored in the same local SQLite file and are not tamper-evident or externally archived.
- Reports are local query results without scheduled delivery, row-level report access rules, or a report-builder UI. Date filters are available on the operations summary screen.
- Only the browser and screen sizes actually covered by recorded acceptance output should be treated as verified.
