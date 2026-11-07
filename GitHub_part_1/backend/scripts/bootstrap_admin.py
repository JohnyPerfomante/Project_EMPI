from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select

from app.core.config import settings
from app.database.session import session
from app.models import Role, User
from app.security.auth import password_hasher


def main():
    config = settings()
    password = config.bootstrap_admin_password.get_secret_value()
    try:
        email = TypeAdapter(EmailStr).validate_python(config.bootstrap_admin_email).lower()
    except ValidationError:
        raise SystemExit("Provide a valid BOOTSTRAP_ADMIN_EMAIL.") from None
    if not 12 <= len(password) <= 128:
        raise SystemExit("Provide BOOTSTRAP_ADMIN_PASSWORD of 12–128 characters.")
    with session() as db, db.begin():
        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            if existing.role != Role.ADMIN or not existing.active:
                raise SystemExit("Address belongs to another user or a blocked account.")
            print("An active administrator already exists at this address.")
            return
        db.add(
            User(
                email=email,
                full_name="Адміністратор",
                role=Role.ADMIN,
                password_hash=password_hasher.hash(password),
            )
        )
    print("Administrator created.")


if __name__ == "__main__":
    main()
