from enum import Enum, Flag
from datetime import datetime

from stability_matrix_tools.models.version import Version

from pydantic import BaseModel, ConfigDict, RootModel


def to_camel(string: str) -> str:
    """Convert to camel case."""
    string = "".join(word.capitalize() for word in string.split("_"))
    if string and string[0].isupper():
        string = string[0].lower() + string[1:]
    return string


class UpdateChannel(Enum):
    stable = "stable"
    preview = "preview"
    development = "development"


class UpdateType(Flag, boundary="keep"):
    normal = 0 << 1
    critical = 1 << 1
    mandatory = 1 << 2


class UpdateInfo(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, arbitrary_types_allowed=True)

    version: Version
    release_date: datetime
    channel: UpdateChannel
    url: str
    changelog: str
    signature: str | None
    type: UpdateType | None


class Updates(RootModel):
    model_config = ConfigDict(alias_generator=to_camel)

    root: list[UpdateInfo]
