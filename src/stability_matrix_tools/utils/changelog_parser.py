import re
from pathlib import Path


def get_latest_chunk(changelog_path: Path | str) -> str | None:
    """Get the latest changelog chunk."""
    changelog = Path(changelog_path).read_text()
    chunks = re.finditer(
        r"(##\s*(v[0-9]+\.[0-9]+\.[0-9]+(?:-(?:[0-9A-Za-z-.]+))?)((?:\n|.)+?))(?=(##\s*v[0-9]+\.[0-9]+\.[0-9]+)|\z)",
        changelog,
    )
    first_chunk = next(chunks, None)

    if first_chunk is None:
        return None

    return first_chunk.group(3).strip()
