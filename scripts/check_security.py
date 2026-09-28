"""Small, value-free regression scan. Full secret scanners remain complementary."""
from pathlib import Path
import re
import sys
import subprocess

ROOT = Path(__file__).resolve().parents[1]
patterns = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE " + r"KEY-----"),
    "unverified-tls": re.compile(r"verify\s*=\s*False"),
    "untrusted-ssh": re.compile(r"AutoAdd" + r"Policy\s*\("),
    "url-credential": re.compile(r"[?&]token="),
    "default-community": re.compile(r"snmp_community[^\n]{0,50}[=:][^\n]{0,20}[\"']public[\"']"),
    "embedded-secret": re.compile(r"(?:SECRET_KEY|AUTHENTICATION_API_KEY|EVOLUTION_API_KEY|POSTGRES_PASSWORD)\s*=\s*[\"'][^\"']{8,}[\"']"),
}


def main():
    failures = []
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    for name in tracked:
        path = ROOT / name
        if not path.is_file():
            continue
        if (path.name.startswith(".env") and path.name != ".env.example") or path.suffix in {".pem", ".key", ".p12", ".pfx"} or "secrets" in path.relative_to(ROOT).parts:
            failures.append(f"{name}: tracked credential/certificate file")
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(x in path.parts for x in (".git", "__pycache__", ".pytest_cache", "secrets")):
            continue
        if path.suffix not in {".py", ".js", ".html", ".yml", ".yaml", ".pem", ".key"}:
            continue
        if path == Path(__file__).resolve() or "tests" in path.parts or path.name.startswith("test_"):
            continue
        for line, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for label, pattern in patterns.items():
                if pattern.search(text):
                    failures.append(f"{path.relative_to(ROOT)}:{line}: {label}")
    for failure in failures:
        print(failure)
    print(f"Security regression scan: {len(failures)} findings")
    return bool(failures)


if __name__ == "__main__":
    sys.exit(main())
