from pathlib import Path
import pytest
from scripts.prepare_runtime import prepare


def test_runtime_secrets_are_persistent_and_existing_configuration_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr('scripts.prepare_runtime.os.chown', lambda *args: None, raising=False)
    names = ('POSTGRES_PASSWORD', 'REDIS_PASSWORD', 'SECRET_KEY', 'NETWORK_CREDENTIAL_KEY',
             'EVOLUTION_API_KEY', 'DATABASE_URL', 'REDIS_URL', 'EVOLUTION_DATABASE_URL', 'EVOLUTION_REDIS_URL')
    for name in names:
        monkeypatch.delenv(name, raising=False)
    directory = tmp_path / 'secrets'
    prepare(tmp_path / 'state', directory)
    saved = {p.name: p.read_text() for p in directory.iterdir()}
    assert len(saved) == 9 and len(set(saved.values())) == 9
    keytab = tmp_path / 'state/BD/sso/http.keytab'
    keytab.write_bytes(b'\x05\x02existing-service-key')
    prepare(tmp_path / 'state', directory)
    assert saved == {p.name: p.read_text() for p in directory.iterdir()}
    assert keytab.read_bytes() == b'\x05\x02existing-service-key'
    monkeypatch.setenv('SECRET_KEY', 'different-existing-secret')
    with pytest.raises(RuntimeError, match='differs from saved'):
        prepare(tmp_path / 'state', directory)
    assert (directory / 'secret_key').read_text() == saved['secret_key']


def test_existing_database_without_original_credentials_fails_before_generation(tmp_path, monkeypatch):
    monkeypatch.setattr('scripts.prepare_runtime.os.chown', lambda *args: None, raising=False)
    monkeypatch.delenv('POSTGRES_PASSWORD', raising=False)
    data = tmp_path / 'state/BD/postgres_data'
    data.mkdir(parents=True)
    (data / 'PG_VERSION').write_text('15')
    with pytest.raises(RuntimeError, match='original .env'):
        prepare(tmp_path / 'state', tmp_path / 'secrets')
    assert not list((tmp_path / 'secrets').iterdir())
