"""Uri helpers"""
from functools import reduce
from urllib import parse

__all__ = ["join"]


def _process_uri_part(uri_part: str) -> str:
    """Process uri part."""
    # Remove leading slashes
    uri_part = uri_part.lstrip("/")

    # Add a trailing slash if not present
    if not uri_part.endswith("/"):
        uri_part += "/"

    return uri_part


def join(*args: str) -> str:
    """Join uri parts."""
    if not args:
        return ""

    if len(args) == 1:
        return args[0]

    processed = (_process_uri_part(arg) for arg in args)

    result = reduce(parse.urljoin, processed)

    # Remove trailing slash
    if result.endswith("/"):
        result = result[:-1]

    return result
