from enum import Enum, Flag
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, field_validator, ValidationError, WrapValidator
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
        return datetime.fromisoformat(value[0])


DateTimeOffset = Annotated[AwareDatetime, WrapValidator(validate_timestamp)]


class UpdateChannel(Enum):
    stable = "stable"
    preview = "preview"
    development = "development"


class UpdateType(Flag, boundary="keep"):
    normal = 0 << 1
    critical = 1 << 1
    mandatory = 1 << 2


class UpdateInfo(BaseModel):
    version: str
    release_date: DateTimeOffset
    channel: UpdateChannel
    url: str
    changelog: str
    signature: str | None = None
    type: UpdateType | None = None

    # noinspection PyMethodParameters
    @field_validator('release_date', 'release_date', mode='before')
    def split_str(cls, v):
        if isinstance(v, str):
            return v.split('|')
        return v

    class Config:
        alias_generator = to_camel
        arbitrary_types_allowed = True
