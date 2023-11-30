import pytest

from stability_matrix_tools.utils import uris


@pytest.mark.parametrize(
    "expected,parts",
    [
        # No slashes
        ("https://example.org/abc", ("https://example.org/", "abc")),
        # Trailing slash on base
        ("https://example.org/abc", ("https://example.org", "abc")),
        # Leading slash on part
        ("https://example.org/abc", ("https://example.org", "/abc")),
        # Trailing slash on part
        ("https://example.org/abc", ("https://example.org", "abc/")),
        # Both slashes on part
        ("https://example.org/abc", ("https://example.org", "/abc/")),
        # Multiple parts
        ("https://example.org/abc/def", ("https://example.org", "abc", "def")),
        # Url escape
        ("https://example.org/abc%2Bdef", ("https://example.org", "abc+def")),
    ],
)
def test_join(expected, parts):
    assert uris.join(*parts) == expected
