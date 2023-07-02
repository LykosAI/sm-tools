from enum import Enum, Flag
from datetime import datetime, timezone
from typing_extensions import Annotated

from pydantic import BaseModel, ValidationError, WrapValidator, Field, field_serializer
from pydantic.types import AwareDatetime


def to_camel(string: str) -> str:
    """Convert to camel case."""
    string = "".join(word.capitalize() for word in string.split("_"))
    if string and string[0].isupper():
        string = string[0].lower() + string[1:]
    return string


def validate_timestamp(value, handler):
    try:
        return handler(value)
    except ValidationError:
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value[0]).replace(tzinfo=timezone.utc)


DateTimeOffset = Annotated[AwareDatetime, WrapValidator(validate_timestamp)]


class UpdateChannel(Enum):
    stable = "stable"
    preview = "preview"
    development = "development"


class UpdateType(Flag):
    normal = 1 << 0
    critical = 1 << 1
    mandatory = 1 << 2


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
