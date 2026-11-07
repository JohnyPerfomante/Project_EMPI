from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import fail
from app.models import Course, SystemSetting
from app.schemas.analysis import AnalysisSettings

ANALYSIS_KEY = "analysis"
WORKER_KEY = "worker"


def setting_row(db: Session, key: str, *, lock: bool = False) -> SystemSetting | None:
    if lock:
        db.execute(insert(SystemSetting).values(setting_key=key, setting_value={}).on_conflict_do_nothing())
    return db.get(SystemSetting, key, with_for_update=lock)


def validate_configuration(values: dict) -> AnalysisSettings:
    try:
        return AnalysisSettings.model_validate(values)
    except ValidationError as error:
        fail(422, "invalid_configuration", error.errors()[0]["msg"].removeprefix("Value error, "))


def analysis_config(db: Session, course: Course | None = None) -> AnalysisSettings:
    row = setting_row(db, ANALYSIS_KEY)
    return AnalysisSettings.model_validate(
        (row.setting_value if row else {}) | (course.analysis_overrides if course else {})
    )
