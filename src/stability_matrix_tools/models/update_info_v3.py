from __future__ import annotations

from pydantic import BaseModel, Field

from stability_matrix_tools.models.update_base import UpdateChannel
from stability_matrix_tools.models.update_info import UpdateInfo


class UpdateManifest(BaseModel):
    updates: dict[UpdateChannel, UpdatePlatforms] = Field(default_factory=dict)


class UpdatePlatforms(BaseModel):
    win_x64: UpdateInfo | None = Field(alias="win-x64", default=None)
    linux_x64: UpdateInfo | None = Field(alias="linux-x64", default=None)
    macos_arm64: UpdateInfo | None = Field(alias="macos-arm64", default=None)

    class Config:
        populate_by_name = True
