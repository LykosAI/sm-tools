def to_camel(string: str) -> str:
    """Convert to camel case."""
    string = "".join(word.capitalize() for word in string.split("_"))
    if string and string[0].isupper():
        string = string[0].lower() + string[1:]
    return string
