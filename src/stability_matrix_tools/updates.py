"""Manages automatic updates"""
from stability_matrix_tools.models.update_info import UpdateInfo
from stability_matrix_tools.models.settings import env

import typer
import httpx

app = typer.Typer()


@app.command()
def check():
    """Checks for updates"""
    typer.echo("Checking for updates...")

    # Use a cache-control 0 header to ensure we get the latest version
    headers = {"Cache-Control": "no-cache"}
    res = httpx.get(env.update_manifest_url, headers=headers)
    res.raise_for_status()

    updates = UpdateInfo.model_validate_json(res.text)
    typer.echo(updates)
