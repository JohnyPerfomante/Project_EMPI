from datetime import UTC, datetime, timedelta
from functools import lru_cache
from hashlib import sha256
from secrets import token_urlsafe
from typing import Annotated

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import fail
from app.database.session import get_db
from app.models import AuthSession, LoginThrottle, Role, User
from app.services.audit import audit

DB = Annotated[Session, Depends(get_db)]
password_hasher = PasswordHasher()
ACCESS_COOKIE = "empi_access"
REFRESH_COOKIE = "empi_refresh"
ISSUER = "osvitnii-protses"


def now():
    return datetime.now(UTC)


def digest(value: str) -> str:
    return sha256(value.encode()).hexdigest()


@lru_cache
def jwt_key() -> str:
    return settings().jwt_secret.get_secret_value() or token_urlsafe(48)


@lru_cache
def dummy_hash() -> str:
    return password_hasher.hash(token_urlsafe(32))


def verify_password(value: str, hashed: str) -> bool:
    try:
        return password_hasher.verify(hashed, value)
    except (VerificationError, InvalidHashError):
        return False


def require_login():
    fail(401, "unauthorized", "Увійдіть до системи, щоб продовжити.")


def current_user(request: Request, db: DB) -> User:
    token = request.cookies.get(ACCESS_COOKIE)
    if token is None:
        require_login()
    try:
        claims = jwt.decode(
            token,
            jwt_key(),
            algorithms=["HS256"],
            issuer=ISSUER,
            options={"require": ["exp", "sub", "sid", "iss"]},
        )
        user_id, session_id = int(claims["sub"]), int(claims["sid"])
    except (jwt.InvalidTokenError, TypeError, ValueError):
        require_login()
    user = db.scalar(
        select(User)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(
            User.id == user_id,
            User.active.is_(True),
            AuthSession.id == session_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now(),
        )
    )
    if user is None or (user.demo and settings().app_env == "production"):
        require_login()
    request.state.actor_id = user.id
    return user


Actor = Annotated[User, Depends(current_user)]


def staff_user(user: Actor) -> User:
    if user.role not in (Role.TEACHER, Role.ADMIN):
        fail(403, "forbidden", "Для цієї дії потрібні права викладача або адміністратора.")
    return user


def admin_user(user: Actor) -> User:
    if user.role != Role.ADMIN:
        fail(403, "forbidden", "Для цієї дії потрібні права адміністратора.")
    return user


Staff = Annotated[User, Depends(staff_user)]
Admin = Annotated[User, Depends(admin_user)]


def throttle(db: Session, email: str, ip: str, *, registration: bool = False):
    time = now()
    window = time.replace(minute=time.minute - time.minute % 10, second=0, microsecond=0)
    prefix = "register:" if registration else ""
    attempt_limit = settings().registration_limit if registration else settings().login_limit
    for key, limit in (
        (digest(f"{prefix}ip:{ip}"), attempt_limit * 3),
        (digest(f"{prefix}account:{email}"), attempt_limit),
    ):
        statement = insert(LoginThrottle).values(key=key, attempts=1, window_start=window)
        attempts = db.scalar(
            statement.on_conflict_do_update(
                index_elements=[LoginThrottle.key],
                set_={"attempts": LoginThrottle.attempts + 1, "window_start": window},
                where=LoginThrottle.window_start == window,
            ).returning(LoginThrottle.attempts)
        )
        if attempts is None:
            row = db.get(LoginThrottle, key, with_for_update=True)
            if row.window_start < window:
                row.window_start, row.attempts = window, 1
                attempts = 1
            else:
                attempts = row.attempts
        if attempts > limit:
            db.commit()
            operation = "реєстрації" if registration else "входу"
            fail(429, "rate_limited", f"Забагато спроб {operation}. Повторіть пізніше.")


def issue_cookies(response: Response, auth: AuthSession, refresh: str):
    config = settings()
    access_seconds = config.access_minutes * 60
    token = jwt.encode(
        {
            "sub": str(auth.user_id),
            "sid": str(auth.id),
            "iss": ISSUER,
            "exp": now() + timedelta(seconds=access_seconds),
        },
        jwt_key(),
        algorithm="HS256",
    )
    options = {"secure": config.cookie_secure, "httponly": True, "samesite": "lax"}
    response.set_cookie(
        ACCESS_COOKIE, token, path="/api/v1", max_age=access_seconds if auth.remember else None, **options
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        path="/api/v1/auth",
        max_age=max(0, int((auth.expires_at - now()).total_seconds())) if auth.remember else None,
        **options,
    )


def login(db: Session, response: Response, email: str, password: str, remember: bool, ip: str) -> User:
    throttle(db, email, ip)
    user = db.scalar(select(User).where(User.email == email).with_for_update())
    valid = verify_password(password, user.password_hash if user else dummy_hash())
    if not user or not valid or not user.active or (user.demo and settings().app_env == "production"):
        db.commit()
        fail(401, "invalid_credentials", "Невірна електронна пошта або пароль.")
    if password_hasher.check_needs_rehash(user.password_hash):
        user.password_hash = password_hasher.hash(password)
    refresh = token_urlsafe(48)
    user.last_login_at = now()
    auth = AuthSession(
        user_id=user.id,
        refresh_hash=digest(refresh),
        remember=remember,
        expires_at=now() + timedelta(days=settings().refresh_days if remember else 1),
    )
    db.add(auth)
    audit(db, user.id, "login", "user", user.id, ip_address=ip)
    db.commit()
    issue_cookies(response, auth, refresh)
    return user


def find_refresh(db: Session, request: Request) -> AuthSession | None:
    refresh = request.cookies.get(REFRESH_COOKIE)
    if not refresh:
        return None
    return db.scalar(
        select(AuthSession)
        .where(
            AuthSession.refresh_hash == digest(refresh),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now(),
        )
        .with_for_update()
    )
