# REP_ZAP_INV

Unified IT management platform deployed with Docker Compose.

## Quick Start

Requirements: Git, Docker Engine with Docker Compose v2, OpenSSL, and Python 3.

```bash
git clone https://github.com/ZQRey/REP_ZAP_INV.git
cd REP_ZAP_INV
chmod +x scripts/init-env.sh
./scripts/init-env.sh
docker compose config
docker compose up --build
```

`scripts/init-env.sh` creates `.env` only when it does not already exist. It copies `.env.example`, generates independent cryptographically secure values with `openssl rand -hex 32`, and builds the PostgreSQL/Redis/Evolution connection URLs using Docker service names `postgres-db` and `redis`.

The generated `.env` is mode `600` and is ignored by Git. Do not commit it. Running the initializer again preserves an existing `.env` and therefore preserves encryption/signing keys and database passwords.

If Compose reports `Run ./scripts/init-env.sh first`, initialize the environment before starting the stack:

```bash
./scripts/init-env.sh
docker compose config
docker compose up --build
```

For production, review optional values such as `CORS_ORIGINS`, `NETWORK_ALLOWED_CIDRS`, and LDAP settings in `.env` before exposing the service externally.
