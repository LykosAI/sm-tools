from __future__ import annotations

from sm_tools.models.settings import env
from sm_tools.progress import RichProgressListener
from sm_tools.uploader import Uploader

from pathlib import Path
from urllib.parse import urljoin
from typing import Annotated, TypeVar

import httpx
import typer
from typer import Option

T = TypeVar("T")
ConfirmType = Annotated[bool, Option("--yes", "-y", help="Confirm action")]

app = typer.Typer()


def assert_exists(self, *target: T, msg: str) -> T:
    """Assert that objects are truthy."""
    if not all(target):
        typer.echo(f"❌ [yellow]{msg}")
        raise SystemExit(1)
    return target


@app.command()
def upload(
    file_path: Path,
    b2_path: str,
    confirm: ConfirmType = False,
):
    """Upload a file to a B2 bucket."""

    file = file_path.resolve()
    assert_exists(file, msg=f"File {file_path} does not exist.")

    uploader = Uploader(
        api_id=env.b2_api_id,
        api_key=env.b2_api_key,
        bucket_name=env.b2_bucket_name,
    )

    with RichProgressListener("Uploading...", transient=True) as pbar:
        uploader.upload(str(file), b2_path, pbar)

    result = urljoin(env.cdn_root, b2_path)
    typer.echo(f"✅ Uploaded at: {result}")


