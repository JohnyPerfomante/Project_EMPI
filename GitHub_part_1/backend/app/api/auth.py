from secrets import token_urlsafe

from fastapi import APIRouter, Request, Response

from app.core.config import settings
from app.models import User
from app.schemas.catalog import LoginIn, RegisterIn, UserView
from app.schemas.common import Message
from app.security.auth import (
    ACCESS_COOKIE,
    DB,
    REFRESH_COOKIE,
    Actor,
    digest,
    find_refresh,
    issue_cookies,
    login,
    now,
    require_login,
)
from app.services.audit import audit
from app.services.registration import register_account

router = APIRouter(prefix="/auth", tags=["Авторизація"])


@router.post("/register", response_model=UserView, status_code=201)
def register(body: RegisterIn, request: Request, db: DB):
    return register_account(db, body, request.client.host if request.client else "unknown")


@router.post("/login", response_model=UserView)
def sign_in(body: LoginIn, request: Request, response: Response, db: DB):
    return login(
        db,
        response,
        body.email.lower(),
        body.password,
        body.remember,
        request.client.host if request.client else "unknown",
    )


@router.get("/me", response_model=UserView)
def me(user: Actor):
    return user


@router.post("/refresh", response_model=UserView)
def refresh(request: Request, response: Response, db: DB):
    auth = find_refresh(db, request)
    if auth is None:
        require_login()
    user = db.get(User, auth.user_id)
    if not user.active or (user.demo and settings().app_env == "production"):
        require_login()
    secret = token_urlsafe(48)
    auth.refresh_hash = digest(secret)
    db.commit()
    issue_cookies(response, auth, secret)
    return user


@router.post("/logout", response_model=Message)
def sign_out(request: Request, response: Response, db: DB):
    auth = find_refresh(db, request)
    if auth:
        auth.revoked_at = now()
        audit(db, auth.user_id, "logout", "user", auth.user_id)
        db.commit()
    response.delete_cookie(ACCESS_COOKIE, path="/api/v1", secure=settings().cookie_secure, httponly=True)
    response.delete_cookie(
        REFRESH_COOKIE, path="/api/v1/auth", secure=settings().cookie_secure, httponly=True
    )
    return {"message": "Сесію завершено."}
