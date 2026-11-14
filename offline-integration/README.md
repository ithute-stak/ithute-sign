# IthuteSign Offline Integration — v0.7 verification preparation

**Offline source only. No production deployment or hardware signing.**

## New in v0.7
- Added an explicit retry-identity regression test. Two attempts for the same staged evidence must retain the exact evidence ID and SHA-256 digest, and neither may mark a contract signed.
- Tightened the evidence ciphertext assertion.
- Included the encrypted outbox, recovery audits, and Windows verification script.

## Run on Windows with .NET 8 SDK
```powershell
powershell -ExecutionPolicy Bypass -File .\verify-windows.ps1
```

## Required before production readiness
- Run .NET tests and capture output.
- Verify authenticated LoanHub evidence API and server-side idempotency.
- Test physical Wacom STU-540 and signed PDF lifecycle.
- Add interprocess locking, key provisioning, ACLs, orphan recovery and scheduling.
- Reconcile with existing WinUI client before activation.

**Tests authored, not executed in authoring environment.**