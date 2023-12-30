from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_serializer

from stability_matrix_tools.models.update_base import DateTimeOffset, UpdateChannel, UpdateType


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
    macos_arm64: UpdateInfo | None = Field(alias="macos-arm64", default=None)
