"""Uri helpers"""
from functools import reduce
from urllib import parse

__all__ = ["join"]


def join(*args: str) -> str:
    """Join uri parts."""
    if not args:
        return ""

    if len(args) == 1:
        return args[0]

    # Add slash after first arg if not present
    if not args[0].endswith("/"):
        args = (args[0] + "/",) + args[1:]

    # Remove leading slash from args after first
    args = (args[0],) + tuple(arg.lstrip("/") for arg in args[1:])

    return reduce(parse.urljoin, args)
