# Release Acceptance Audit — 2026-09-28

Goal: assess whether the current product is operationally releasable, not merely secure.

## What is automatically verified
- Unified application imports/mounts Portal, Cartridge, Repair and Location.
- Primary browser pages respond and their repository-hosted JS/CSS assets exist.
- Alpine click/submit/change handlers used by the four primary pages resolve to functions in their corresponding JavaScript modules.
- Frontend authentication transport is shared and tokens are not put into URLs.
- Authorization policy coverage/branch isolation/IDOR tests remain part of pytest.
- Alembic schema and PostgreSQL migration/integrity tests are CI gates.
- Notification retry/idempotency/crash-recovery tests are CI gates.
- Python/JavaScript static checks and Docker image build are CI gates.
- /health now verifies live database connectivity; Compose marks unified-server healthy only after this succeeds and Nginx waits for application readiness.

## Release blockers requiring the deployment environment
These cannot be honestly certified from GitHub source alone:
1. Active Directory bind/search/sync using the customer's real DC/DNS/certificate path.
2. Evolution API instance creation/QR/session/send against the customer's WhatsApp account.
3. SSH known_hosts and SNMP/Omada/MikroTik access to real switches.
4. Actual TLS certificate/key mounted into nginx/ssl and client trust.
5. PostgreSQL upgrade of the customer's existing data, including 0005 and the one-time network credential encryption pass.
6. Browser acceptance on the customer's target browsers and network: every workflow should be exercised with realistic roles/branches.

## Required acceptance walkthrough
- Login: local superadmin; local normal user; AD user; invalid credentials; logout/session expiry.
- Portal: branch selector, stats, users, branches/floors, settings, LDAP test/sync, navigation to all three modules.
- Cartridge: registry CRUD, search/QR, accept, vendor batch/print, return, issue/bulk issue, reports Excel/PDF, WhatsApp status/QR/test/ready queue.
- Repair: equipment CRUD/AD lookup, accept, send to service/print, return, install workplace, models/sync/suggest, reports/export.
- Location: floor CRUD/map upload, zones/assets placement, create/unplace/move, switch CRUD/test/poll, port settings, trace, simulated event where permitted.
- Operations: restart app/worker/Redis during queued notifications; verify recovery; backup/restore; verify health endpoint and Nginx behavior.

## Readiness statement
The source now contains automated release gates for application pages/assets/UI-handler wiring in addition to security, database, notification and Docker checks. Source inspection cannot establish a numeric 99% availability or guarantee that every real integration works. Production acceptance should be declared only after CI is green on the release commit and the environment-specific walkthrough above passes.

Any failed walkthrough item should be treated as a release bug and fixed before customer handoff.
