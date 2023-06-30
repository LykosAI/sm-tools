from __future__ import annotations

import semver


class Version(semver.Version):
    @classmethod
    def _parse(cls, version) -> Version:
        return cls.parse(version)

    @classmethod
    def __get_validators__(cls):
        """Yields validator methods for pydantic models."""
        yield cls._parse
