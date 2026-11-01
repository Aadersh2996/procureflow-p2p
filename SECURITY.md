# Security policy

## Reporting a vulnerability

Please use GitHub's private **Report a vulnerability** flow from the repository's Security tab. Do not include exploit details in a public issue. This is a portfolio simulation with no dedicated security response team; reports will be reviewed as time permits.

## Scope and limitations

ProcureFlow is intended for local evaluation with fictional demo data. It is not a production identity or access-management system and has no real bank, payment-network, or financial institution integration. Demo accounts and passwords are for offline local evaluation only. Do not put real personal, supplier, banking, or payment data into the application.

The application uses a local SQLite database by default. Session signing uses a process-local random key unless `P2P_SESSION_SECRET` is supplied. A local demonstration configuration is not a production deployment configuration.

## Supported versions

Only the current default branch is maintained for this demonstration project.
