import difflib

from rich import print as cp
from rich.markdown import Markdown, Syntax


def print_diff(a, b):
    a = a.splitlines(keepends=True)
    b = b.splitlines(keepends=True)
    diff = difflib.unified_diff(a, b, fromfile="a", tofile="b")

    cp(Syntax("".join(diff), "diff"))
