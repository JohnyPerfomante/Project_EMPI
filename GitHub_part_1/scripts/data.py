"""Portable PostgreSQL backup and restore through Docker Compose (standard library only)."""

import argparse
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def compose(*args, **kwargs):
    return subprocess.run(["docker", "compose", *args], cwd=ROOT, check=True, **kwargs)


def backup(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with path.open("xb") as output:
            created = True
            os.chmod(path, 0o600)
            compose(
                "exec", "-T", "db", "sh", "-c",
                'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" '
                "--format=custom --no-owner --no-privileges",
                stdout=output,
            )
        if not path.stat().st_size:
            raise RuntimeError("Backup is empty")
    except BaseException:
        if created:
            path.unlink(missing_ok=True)
        raise
    print(f"Database backup saved: {path}")


def restore(path):
    with path.open("rb") as source:
        if source.read(5) != b"PGDMP":
            raise SystemExit("Expected a PostgreSQL custom-format dump created by pg_dump.")
    running = compose("ps", "--status", "running", "-q", "api", "worker", capture_output=True, text=True)
    if running.stdout.strip():
        raise SystemExit("Stop api and worker before restoring: docker compose stop api worker")
    query = "SELECT count(*) FROM pg_tables WHERE schemaname = 'public';"
    tables = compose(
        "exec", "-T", "db", "sh", "-c",
        'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -v ON_ERROR_STOP=1 -c "$1"',
        "sh", query, capture_output=True, text=True,
    )
    if tables.stdout.strip() != "0":
        raise SystemExit("Restore requires an empty database. Existing data has been preserved.")
    with path.open("rb") as source:
        compose(
            "exec", "-T", "db", "sh", "-c",
            'exec pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" '
            "--no-owner --no-privileges --exit-on-error --single-transaction",
            stdin=source,
        )
    print("Database restored. Existing account passwords are unchanged; sign in again.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["backup", "restore"])
    parser.add_argument("path", type=Path, help="Path to a private .dump file")
    arguments = parser.parse_args()
    if not (ROOT / ".env").is_file():
        raise SystemExit("Create .env first: python3 scripts/configure.py")
    {"backup": backup, "restore": restore}[arguments.action](arguments.path.resolve())


if __name__ == "__main__":
    main()
