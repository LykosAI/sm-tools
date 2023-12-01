"""Uri helpers"""
from urllib import parse

__all__ = ["join"]


def join(*parts: str, quote: bool = False) -> str:
    """Join uri parts."""
    if not parts:
        return ""

    return parse.urljoin(
        parts[0],
        "/".join(
            (parse.quote_plus(part.strip("/"), safe="/") if quote else part.strip("/"))
            for part in parts[1:]
        ),
    )
