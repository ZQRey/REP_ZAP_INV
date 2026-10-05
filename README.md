# REP_ZAP_INV

Unified IT management platform deployed with Docker Compose.

## Quick Start

Requirements: Docker Engine with Docker Compose v2. Git is needed only to clone the repository.

```bash
git clone https://github.com/ZQRey/REP_ZAP_INV.git
cd REP_ZAP_INV
docker compose up --build
```

No `.env`, host Python, OpenSSL or manual directory preparation is required. Compose prepares writable upload directories, generates independent random secrets in `secrets/runtime`, waits for PostgreSQL, applies Alembic migrations and initializes the administrator. Application processes start only after successful preparation and migrations.

On an empty database, sign in with **admin / admin123**. The portal requires a new password of at least 8 characters before granting access to modules or their APIs. Existing accounts are preserved; repeated startup never resets passwords or creates another administrator.

For background operation use `docker compose up -d --build`. Optional settings can be supplied in `.env` (see `.env.example`); existing deployments with populated `.env` are supported and their keys are preserved. LDAP and switch settings remain configurable in the application.

When moving an existing installation, copy `BD`, `uploads`, `secrets`, `evolution_instances` and the existing `.env` with the project. Preserve file ownership and stop the source stack before copying live database files (or use a database backup/restore). The destination then starts with the same `docker compose up --build`. Do not omit `secrets/runtime`: it contains database credentials and the key needed to decrypt saved switch credentials. Runtime data and secrets are ignored by Git.

## Reverse proxy / TLS topology

REP_ZAP_INV does not terminate TLS locally. The bundled Nginx container listens on HTTP port 80 only and is intended to be an internal upstream for a separate reverse-proxy container or VM in Proxmox VE.

The external reverse proxy is responsible for:
- HTTPS certificates and certificate renewal;
- HTTP-to-HTTPS redirection;
- HSTS and other edge TLS policy;
- forwarding the original `Host`, `X-Forwarded-Proto`, and `X-Forwarded-For` headers.

Configure the external reverse proxy upstream to the REP_ZAP_INV host on TCP port 80. Restrict access to that port at the host/network firewall so only trusted management networks and the external reverse proxy can reach it.
