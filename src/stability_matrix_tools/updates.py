"""Manages automatic updates"""
from stability_matrix_tools.models.update_info import UpdateInfo
from stability_matrix_tools.models.settings import env

import typer
import httpx
from rich import print as cp

app = typer.Typer()


@app.command()
def check():
    """Checks for updates"""
    cp("Checking for updates...")

    # Use a cache-control 0 header to ensure we get the latest version
    headers = {"Cache-Control": "no-cache"}
    url = env.update_manifest_url
    res = httpx.get(url, headers=headers)
    res.raise_for_status()

    cp(f"✅  {url!r} -> ({res.status_code})")
    cp(res.json())

    updates = UpdateInfo.model_validate_json(res.text)
    cp(updates)
