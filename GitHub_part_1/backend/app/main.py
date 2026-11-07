import logging
from uuid import uuid4

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.exceptions import HTTPException

from app.api import administration, auth, courses, questions, reports, submissions, variations
from app.api.common import COMMON_ERRORS
from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()
log = logging.getLogger("empi.api")
app = FastAPI(
    title="Освітній процес · API",
    description="Підсистема перевірки відкритих відповідей студентів.",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)
api = APIRouter(prefix="/api/v1", responses=COMMON_ERRORS)
for router in (
    auth.router,
    administration.router,
    courses.router,
    questions.router,
    variations.router,
    submissions.router,
    reports.router,
):
    api.include_router(router)
app.include_router(api)


def error_response(status, code, message, **extra):
    return JSONResponse({"error": {"code": code, "message": message, **extra}}, status_code=status)


@app.middleware("http")
async def protect_api(request: Request, call_next):
    request_id = str(uuid4())
    if (
        request.url.path.startswith("/api/v1/")
        and request.method in {"POST", "PATCH", "PUT", "DELETE"}
        and request.headers.get("X-EMPI-Request") != "1"
    ):
        response = error_response(403, "csrf", "Для зміни даних потрібен заголовок X-EMPI-Request: 1.")
    else:
        response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith("/api/v1/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(HTTPException)
async def handle_http(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code, headers=exc.headers)
    messages = {404: ("not_found", "Маршрут не знайдено."), 405: ("method_not_allowed", "Метод недоступний.")}
    code, message = messages.get(exc.status_code, ("request_error", "Запит не вдалося виконати."))
    response = error_response(exc.status_code, code, message)
    response.headers.update(exc.headers or {})
    return response


@app.exception_handler(RequestValidationError)
async def handle_validation(request: Request, exc: RequestValidationError):
    fields = [
        {"field": ".".join(str(part) for part in field["loc"]), "rule": field["type"]}
        for field in exc.errors()
    ]
    return error_response(422, "invalid_data", "Перевірте формат і обов’язкові поля запиту.", fields=fields)


@app.exception_handler(IntegrityError)
async def handle_integrity(request: Request, exc: IntegrityError):
    return error_response(409, "data_conflict", "Запис уже існує або пов’язаний об’єкт недоступний.")


@app.exception_handler(OperationalError)
async def handle_database(request: Request, exc: OperationalError):
    return error_response(503, "database_unavailable", "База даних тимчасово недоступна.")


@app.exception_handler(Exception)
async def handle_unknown(request: Request, exc: Exception):
    log.error("unhandled_api_error", extra={"error_type": type(exc).__name__})
    return error_response(500, "internal_error", "Сервіс тимчасово не зміг обробити запит.")


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT"],
    allow_headers=["Content-Type", "X-EMPI-Request"],
)
