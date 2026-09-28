#!/bin/sh
set -eu
umask 077
mkdir -p /run/app-secrets
make_secret() {
  file="/run/app-secrets/$1"
  if [ ! -s "$file" ]; then
    python -c 'import secrets,sys; print(secrets.token_urlsafe(int(sys.argv[2])))' "$file" "$2" > "$file"
  fi
}
make_secret secret_key 48
make_secret network_credential_key 48
echo "Runtime secrets are ready."
