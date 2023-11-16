"""Configuration"""
from __future__ import annotations

from typing import Optional

import pyperclip
import rich
import typer
from typing_extensions import Annotated

from stability_matrix_tools.models.keyring_config import ConfigKey, KeyringConfig

app = typer.Typer(no_args_is_help=True)
cp = rich.print


@app.command(name="set")
def set_config(
        key: ConfigKey,
        value: Annotated[Optional[str], typer.Argument()] = None
):
    """Set a configuration value."""
    with KeyringConfig.load_from_keyring() as config:
        if value is None and key in config:
            del config[ConfigKey(key)]
        else:
            config[ConfigKey(key)] = value

    cp(f"{'Cleared' if value is None else 'Saved'} key {repr(key.value)}")


@app.command(name="set-cp")
def set_cp_config(
    key: ConfigKey
):
    """Set a configuration value from clipboard."""
    value = pyperclip.paste()

    with KeyringConfig.load_from_keyring() as config:
        if value is None and key in config:
            del config[ConfigKey(key)]
        else:
            config[ConfigKey(key)] = value

    cp(f"Saved key {repr(key.value)} from clipboard ({len(value)} chars)")


@app.command()
def show():
    """Show the current configuration."""
    config = KeyringConfig.load_from_keyring()
    cp(config.to_keys_json())
