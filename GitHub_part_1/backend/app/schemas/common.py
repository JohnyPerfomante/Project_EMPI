from datetime import datetime
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Patch(Input):
    @model_validator(mode="after")
    def forbid_explicit_nulls(self):
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"Поле {name} не може бути порожнім.")
        return self


class View(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RecordView(View):
    id: int
    created_at: datetime


class ErrorDetail(BaseModel):
    code: str
    message: str
    fields: list[dict[str, str]] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Message(BaseModel):
    message: str


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    offset: int
    limit: int


Name = Annotated[str, StringConstraints(min_length=2, max_length=160)]
ShortName = Annotated[str, StringConstraints(min_length=1, max_length=80)]
Description = Annotated[str, StringConstraints(max_length=3000)]
MaterialText = Annotated[str, StringConstraints(min_length=5, max_length=4000)]
Year = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}/[0-9]{4}$")]
