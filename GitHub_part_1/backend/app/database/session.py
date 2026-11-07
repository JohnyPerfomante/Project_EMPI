from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


@lru_cache
def engine():
    return create_engine(settings().database_url, pool_pre_ping=True, hide_parameters=True)


def session() -> Session:
    return sessionmaker(engine(), expire_on_commit=False)()


def get_db():
    with session() as db:
        yield db
