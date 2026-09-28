# Production Readiness Audit — 2026-09-28

Scope: current GitHub main after stages 1–10, plus remediation in this audit branch. Static code/configuration review; no access to production PostgreSQL, AD, Evolution sessions, switches, DNS, TLS certificates or runtime metrics.

## Executive status

No known CRITICAL finding remains in the reviewed source. Two HIGH findings discovered during the final audit are remediated in this branch. Remaining findings are MEDIUM/LOW and should be scheduled rather than silently treated as complete.

## Findings

### HIGH — Notification could remain PROCESSING forever after worker crash — FIXED
**Files:** SHARED/notification_worker.py, tests/services/test_notification_service.py, docker-compose.yml

The original outbox worker committed PROCESSING before the provider call. A crash after that commit made the row ineligible forever. PROCESSING now carries a lease timestamp; stale leases are reclaimed with row locking and attempts continue through the retry/dead-letter policy. Regression coverage added.

### HIGH — Network device credentials stored as plaintext — FIXED
**Files:** SHARED/models.py, SHARED/credential_crypto.py, SHARED/security_config.py, alembic/versions/0005_network_credentials.py, scripts/encrypt_network_credentials.py

Switch passwords and SNMP communities are now encrypted at application level before persistence. Production requires NETWORK_CREDENTIAL_KEY. Existing databases require the explicit post-migration encryption pass documented below. API response models continue to exclude credential fields.

### MEDIUM — Time columns are predominantly timezone-naive — OPEN
Many models/services still use DateTime + datetime.utcnow(). This is internally UTC by convention but loses timezone semantics at the database/type boundary. A future migration should convert operational timestamps to timezone-aware UTC/TIMESTAMPTZ in a controlled schema migration. Do not mass-edit datetime calls without migrating existing data and compatibility tests.

### MEDIUM — Network credential username and extra_params remain plaintext — OPEN
Passwords and SNMP communities are encrypted. username is generally non-secret. extra_params may contain vendor-specific secrets (for example enable/API values) and therefore should be replaced with a typed encrypted credential object rather than arbitrary JSON.

### MEDIUM — SNMPv2c compatibility remains available — OPEN
Legacy switches may still use community-based SNMP. SNMPv3 authPriv should be the default for capable devices. v2c should be documented as compatibility-only and constrained to management networks.

### MEDIUM — Frontend remains structurally monolithic — OPEN
Authentication/API transport is centralized and URL-token leakage is prevented, but large legacy JS files remain. Split by domain only when adding features; avoid a rewrite solely for file size.

### MEDIUM — Container image/dependency reproducibility — OPEN
Python application dependencies use bounded/minimum versions rather than a generated lock with hashes. Compose images such as nginx:alpine, redis:7-alpine and Evolution API are not digest-pinned. Production releases should pin tested versions/digests and use a dependency lock.

### MEDIUM — Evolution API delivery is at-least-once, not exactly-once — OPEN
The local outbox is idempotent before provider submission and crash-safe after remediation. A process crash after Evolution accepts a message but before SENT is committed can still cause a retry. Exactly-once requires provider-supported idempotency/message reconciliation; treat delivery as at-least-once.

### LOW — Mypy remains advisory — OPEN
CI runs type checking but does not block merges. Gradually type service/repository boundaries before enabling strict blocking.

### LOW — Legacy compatibility modules remain — OPEN
CARTRIDGE app database/model/config facades remain for compatibility. Architecture tests should continue ensuring canonical SHARED Base/session/models are authoritative.

## Verified controls

- Required production secrets and fail-fast configuration.
- No tracked TLS private key in the reviewed tree.
- Explicit production CORS origins; DEBUG/DEMO forbidden.
- JWT issuer/audience/expiry policy and login rate limiting.
- Central authorization registry, branch-scoped ORM enforcement and IDOR regression tests.
- One canonical SQLAlchemy architecture and Alembic-only schema evolution.
- Atomic document numbering.
- Network target allowlists, TLS verification and SSH known-host validation.
- Network polling no longer changes authoritative Asset location from one MAC observation.
- Durable notification outbox with retry/dead state and crashed-worker recovery.
- Shared frontend auth transport; no bearer token in URL/localStorage persistence.
- Non-root application image and no direct host exposure for PostgreSQL/Redis/Evolution.
- HTTPS redirect/HSTS/security headers in Nginx.
- CI gates for security/static checks, pytest, PostgreSQL migrations/isolation and Docker build.

## Required deployment sequence for this audit

1. Back up PostgreSQL and verify restore procedure.
2. Generate a stable high-entropy NETWORK_CREDENTIAL_KEY and store it in the production secret mechanism. Never rotate it without decrypt/re-encrypt planning.
3. Deploy code/config with the key available to application containers.
4. Run: alembic upgrade head
5. Run once: python scripts/encrypt_network_credentials.py
6. Verify the script reports encryption and rerun it once to confirm idempotency (second run should report zero changes).
7. Restart unified-server and notification-worker.
8. Smoke-test login, branch isolation, Cartridge/Repair transitions, Location switch polling, switch connection tests and WhatsApp queue delivery/retry.
9. Confirm notification rows do not remain PROCESSING beyond the configured lease during a controlled worker restart.

## Release decision

Source-level CRITICAL/HIGH blockers found by this audit are remediated in this branch. Production promotion still requires successful CI plus the deployment/migration and manual runtime smoke tests above; this static audit cannot certify external AD, Evolution, switch/SNMP/SSH, TLS certificate or production database behavior.
