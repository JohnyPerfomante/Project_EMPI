from typing import NoReturn

from fastapi import HTTPException


def fail(status: int, code: str, message: str) -> NoReturn:
    raise HTTPException(status, {"code": code, "message": message})


def missing() -> NoReturn:
    fail(404, "not_found", "Запис не знайдено або він недоступний.")


def conflict(message: str) -> NoReturn:
    fail(409, "conflict", message)
