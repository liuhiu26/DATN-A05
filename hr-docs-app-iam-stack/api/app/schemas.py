"""Pydantic model cho body request (validate SAU khi đã phân quyền, để request bị từ chối luôn trả 403)."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .errors import HttpError

Role = Literal["employee", "manager", "admin"]
Classification = Literal["internal", "confidential"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DocumentCreate(Strict):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=100_000)
    classification: Classification = "internal"


class DocumentUpdate(Strict):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, max_length=100_000)
    classification: Classification | None = None


class EmployeePatch(Strict):
    fullName: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=300)
    position: str | None = Field(default=None, max_length=120)
    role: Role | None = None
    salary: int | None = Field(default=None, ge=0)
    department: str | None = None
    isActive: bool | None = None


class UserCreate(Strict):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)  # cho phép domain nội bộ .local
    password: str = Field(min_length=8, max_length=128)
    fullName: str = Field(min_length=1, max_length=120)
    role: Role = "employee"
    department: str | None = None
    position: str = ""
    phone: str = ""
    address: str = ""
    salary: int = Field(default=0, ge=0)


def parse(model: type[BaseModel], data) -> BaseModel:
    if not isinstance(data, dict):
        raise HttpError(400, "JSON object expected")
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = ".".join(str(x) for x in first["loc"]) or "body"
        raise HttpError(400, f"{loc}: {first['msg']}") from exc
