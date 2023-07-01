from enum import Enum, Flag
from datetime import datetime
from typing_extensions import Annotated

from pydantic import BaseModel, ValidationError, WrapValidator
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
        return datetime.fromisoformat(value[0])


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
    release_date: DateTimeOffset
    channel: UpdateChannel
    type: UpdateType
    url: str
    changelog: str
    hash_blake3: str
    signature: str

    class Config:
        alias_generator = to_camel
        arbitrary_types_allowed = True
