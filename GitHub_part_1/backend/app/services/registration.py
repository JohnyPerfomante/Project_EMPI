from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import fail
from app.models import Role, User
from app.schemas.catalog import RegisterIn
from app.security.auth import password_hasher, throttle
from app.services.audit import audit


def register_account(db: Session, body: RegisterIn, ip_address: str) -> User:
    email = body.email.lower()
    throttle(db, email, ip_address, registration=True)
    user = db.scalar(
        insert(User)
        .values(
            full_name=body.full_name,
            email=email,
            password_hash=password_hasher.hash(body.password),
            role=Role(body.role),
            active=True,
            demo=False,
        )
        .on_conflict_do_nothing(index_elements=[User.email])
        .returning(User)
    )
    if user is None:
        db.commit()
        fail(409, "email_already_registered", "Обліковий запис із цією електронною поштою вже існує.")
    audit(db, user.id, "register", "user", user.id, ip_address=ip_address, role=user.role)
    db.commit()
    return user
