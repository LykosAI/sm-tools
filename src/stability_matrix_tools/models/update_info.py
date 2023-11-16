from __future__ import annotations
from enum import Enum, Flag
from datetime import datetime, timezone
from typing_extensions import Annotated

from pydantic import BaseModel, ValidationError, WrapValidator, Field, field_serializer
from pydantic.types import AwareDatetime


def validate_timestamp(value, handler):
    try:
        return handler(value)
    except ValidationError:
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value[0]).replace(tzinfo=timezone.utc)


DateTimeOffset = Annotated[AwareDatetime, WrapValidator(validate_timestamp)]


class UpdateChannel(Enum):
    STABLE = "stable"
    PREVIEW = "preview"
    DEVELOPMENT = "development"


class UpdateType(Flag):
    NORMAL = 1 << 0
    CRITICAL = 1 << 1
    MANDATORY = 1 << 2

    @classmethod
    def parse(cls, value: str) -> UpdateType:
        """Parse a string into an UpdateType."""
        result = cls(0)

        if "normal" in value:
            result |= cls.NORMAL
        if "critical" in value:
            result |= cls.CRITICAL
        if "mandatory" in value:
            result |= cls.MANDATORY

        if not result:
            raise ValueError(f"Unknown update type: {value!r}")

        return result


class UpdateInfo(BaseModel):
    version: str
    release_date: DateTimeOffset = Field(alias="releaseDate")
    channel: UpdateChannel
    type: UpdateType
    url: str
    changelog: str
    hash_blake3: str = Field(alias="hashBlake3")
    signature: str

    @field_serializer("release_date")
    def serialize_dt(self, dt: datetime, _info):
        return dt.replace(tzinfo=timezone.utc).isoformat()

    class Config:
        arbitrary_types_allowed = True


class UpdateCollection(BaseModel):
    win_x64: UpdateInfo | None = Field(alias="win-x64", default=None)
    linux_x64: UpdateInfo | None = Field(alias="linux-x64", default=None)
