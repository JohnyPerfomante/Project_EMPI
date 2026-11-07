"""Create a local .env with independent credentials; never overwrite an existing file."""

import secrets
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    target = root / ".env"
    database_password = secrets.token_urlsafe(24)
    replacements = {
        "POSTGRES_PASSWORD": database_password,
        "DATABASE_URL": f"postgresql+psycopg://empi:{database_password}@127.0.0.1:55433/empi",
        "JWT_SECRET": secrets.token_urlsafe(48),
        "DEMO_PASSWORD": secrets.token_urlsafe(24),
    }
    lines = []
    for line in (root / ".env.example").read_text(encoding="utf-8").splitlines():
        key = line.partition("=")[0]
        lines.append(f"{key}={replacements[key]}" if key in replacements else line)
    try:
        with target.open("x", encoding="utf-8", newline="\n") as output:
            target.chmod(0o600)
            output.write("\n".join(lines) + "\n")
    except FileExistsError:
        raise SystemExit(".env already exists; it has been preserved. Edit it manually if needed.") from None
    print("Created .env. Read DEMO_PASSWORD there after seeding the demo accounts.")
    print("Run: docker compose up -d --build")


if __name__ == "__main__":
    main()
