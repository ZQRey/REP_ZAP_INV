"""Disposable CI-only PostgreSQL, loopback-bound, with a fresh random password."""
import os
import secrets
import subprocess
import time
from pathlib import Path
import psycopg2

if os.getenv("GITHUB_ACTIONS") != "true":
    raise SystemExit("This launcher is restricted to disposable GitHub Actions runners")
password = secrets.token_urlsafe(32)
print("::add-mask::" + password, flush=True)
env = dict(os.environ, POSTGRES_PASSWORD=password)
subprocess.run(["docker", "run", "--detach", "--rm", "--name", "rep-zap-migration-test",
                "--publish", "127.0.0.1:55432:5432", "--env", "POSTGRES_PASSWORD",
                "--env", "POSTGRES_USER=migration_test", "--env", "POSTGRES_DB=rep_zap_migration_test",
                "postgres:15"], env=env, check=True, stdout=subprocess.DEVNULL)
for attempt in range(60):
    try:
        connection = psycopg2.connect(host="127.0.0.1", port=55432, user="migration_test",
                                      password=password, dbname="rep_zap_migration_test", connect_timeout=2)
        connection.close()
        break
    except psycopg2.OperationalError:
        time.sleep(1)
else:
    raise SystemExit("PostgreSQL readiness timeout")
url = f"postgresql+psycopg2://migration_test:{password}@127.0.0.1:55432/rep_zap_migration_test"
print("::add-mask::" + url, flush=True)
with Path(os.environ["GITHUB_ENV"]).open("a", encoding="utf-8") as stream:
    stream.write("MIGRATION_TEST_DATABASE_URL=" + url + "\n")
