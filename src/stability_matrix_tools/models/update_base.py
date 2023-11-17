from __future__ import annotations
from enum import Enum, Flag
from datetime import datetime, timezone
from typing_extensions import Annotated

from pydantic import ValidationError, WrapValidator
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
