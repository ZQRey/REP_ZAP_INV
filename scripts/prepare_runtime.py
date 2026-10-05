"""Idempotent Compose preparation; existing database credentials are never rotated."""
import os
import secrets
from pathlib import Path
from urllib.parse import quote


def prepare(root=Path('/state'), secret_dir=Path('/run/app-secrets')):
    secret_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(secret_dir, 0o750)
    os.chown(secret_dir, 10001, 10001)

    def provision(name, factory):
        path = secret_dir / name.lower()
        supplied = os.getenv(name, '')
        if path.exists():
            value = path.read_text().strip()
            if supplied and supplied != value:
                raise RuntimeError(f'{name} differs from saved runtime configuration')
        else:
            value = supplied or factory()
            with path.open('x') as output:
                output.write(value + '\n')
        os.chown(path, 10001, 10001)
        os.chmod(path, 0o640)
        return value

    if ((root / 'BD/postgres_data/PG_VERSION').exists()
            and not (secret_dir / 'postgres_password').exists()
            and not os.getenv('POSTGRES_PASSWORD')):
        raise RuntimeError('Existing PostgreSQL data requires its original .env or saved secrets/runtime directory')
    password = provision('POSTGRES_PASSWORD', lambda: secrets.token_urlsafe(48))
    redis = provision('REDIS_PASSWORD', lambda: secrets.token_urlsafe(48))
    for name in ('SECRET_KEY', 'NETWORK_CREDENTIAL_KEY', 'EVOLUTION_API_KEY'):
        provision(name, lambda: secrets.token_urlsafe(48))
    provision('DATABASE_URL', lambda: f'postgresql://app_user:{quote(password, safe="")}@postgres-db:5432/it_management')
    provision('REDIS_URL', lambda: f'redis://:{quote(redis, safe="")}@redis:6379/0')
    provision('EVOLUTION_DATABASE_URL', lambda: f'postgresql://app_user:{quote(password, safe="")}@postgres-db:5432/evolution')
    provision('EVOLUTION_REDIS_URL', lambda: f'redis://:{quote(redis, safe="")}@redis:6379/1')
    # Production stores data in PostgreSQL; preserve ownership of the checkout's
    # BD parent and never touch PostgreSQL/Redis data directory ownership.
    (root / 'BD').mkdir(parents=True, exist_ok=True)
    os.chmod(root / 'BD', 0o755)
    for relative in ('uploads', 'uploads/maps', 'secrets/ssh'):
        path = root / relative
        path.mkdir(parents=True, exist_ok=True)
        os.chown(path, 10001, 10001)
        os.chmod(path, 0o750)
    print('Runtime configuration and writable directories ready')


if __name__ == '__main__':
    prepare()
