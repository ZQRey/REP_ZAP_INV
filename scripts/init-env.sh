#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
EXAMPLE_FILE="$ROOT_DIR/.env.example"

if [[ -e "$ENV_FILE" ]]; then
  echo ".env already exists; leaving it unchanged."
  exit 0
fi
if [[ ! -f "$EXAMPLE_FILE" ]]; then
  echo "ERROR: $EXAMPLE_FILE not found." >&2
  exit 1
fi
if ! command -v openssl >/dev/null 2>&1; then
  echo "ERROR: openssl is required to generate deployment secrets." >&2
  exit 1
fi

postgres_password="$(openssl rand -hex 32)"
redis_password="$(openssl rand -hex 32)"
secret_key="$(openssl rand -hex 32)"
network_key="$(openssl rand -hex 32)"
evolution_key="$(openssl rand -hex 32)"

cp "$EXAMPLE_FILE" "$ENV_FILE"
chmod 600 "$ENV_FILE"

python3 - "$ENV_FILE" "$postgres_password" "$redis_password" "$secret_key" "$network_key" "$evolution_key" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
pg, redis, secret, network, evolution = sys.argv[2:]
values = {
    "POSTGRES_PASSWORD": pg,
    "DATABASE_URL": f"postgresql://app_user:{pg}@postgres-db:5432/it_management",
    "REDIS_PASSWORD": redis,
    "REDIS_URL": f"redis://:{redis}@redis:6379/0",
    "SECRET_KEY": secret,
    "NETWORK_CREDENTIAL_KEY": network,
    "EVOLUTION_API_KEY": evolution,
    "EVOLUTION_DATABASE_URL": f"postgresql://app_user:{pg}@postgres-db:5432/evolution",
    "EVOLUTION_REDIS_URL": f"redis://:{redis}@redis:6379/1",
}
lines = path.read_text().splitlines()
out = []
for line in lines:
    key = line.split("=", 1)[0] if "=" in line else None
    out.append(f"{key}={values[key]}" if key in values else line)
path.write_text("\n".join(out) + "\n")
PY

echo "Created $ENV_FILE with generated secrets (mode 600)."
echo "Next: docker compose config && docker compose up --build"
