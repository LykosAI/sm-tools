"""Manages automatic updates"""
from stability_matrix_tools.models.update_info import Updates
from stability_matrix_tools.models.settings import env

import typer
import httpx

app = typer.Typer()


@app.command()
def check():
    """Checks for updates"""
    typer.echo("Checking for updates...")

    res = httpx.get(env.update_manifest_url)
    res.raise_for_status()

    updates = Updates.model_validate_json(res.text)
    typer.echo(updates)
