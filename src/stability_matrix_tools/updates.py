"""Manages automatic updates"""
import base64
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urljoin

from stability_matrix_tools.models.update_info import UpdateInfo, UpdateType
from stability_matrix_tools.models.settings import env
from stability_matrix_tools.utils import signing
from stability_matrix_tools.utils.stream_hash import blake3_hash_file

import typer
import httpx
from rich import print as cp

from stability_matrix_tools.utils.cf_cache import cache_purge
from stability_matrix_tools.utils.progress import RichProgressListener
from stability_matrix_tools.utils.uploader import Uploader

app = typer.Typer()


def info_sign_data(info: UpdateInfo) -> str:
    """Returns the data to be signed"""
    return ";".join(
        [
            info.version,
            info.release_date,
            info.channel,
            info.type,
            info.url,
            info.changelog,
            info.hash_blake3,
        ]
    )


# noinspection PyShadowingBuiltins
def sign_update(
        version: str,
        release_date: datetime,
        channel: str,
        type: UpdateType,
        url: str,
        changelog: str,
        hash_blake3: str,
) -> str:
    """
    Signs an update info.
    Returns base64 encoded signature.
    """
    # Signature is of the semicolon separated values:
    # version, releaseDate, channel, type, url, changelog, hash_blake3"
    data = ";".join(
        [
            version,
            release_date.isoformat(),
            channel,
            str(type.value),
            url,
            changelog,
            hash_blake3,
        ]
    )
    cp(f"Data to sign: {data!r}")

    private_key = signing.get_private_key_keyring()
    if not private_key:
        raise RuntimeError("Private key not found.")

    signature = private_key.sign(data.encode("utf-8"))
    return base64.b64encode(signature).decode("utf-8")


@app.command()
def publish(
    version: str,
    url: str,
    changelog: str,
    channel: str = "stable",
    update_type: UpdateType = 1,
    b2_path: str = "update.json",
):
    """Publishes an update"""
    # Like publish_manual, but download the file to get blake3 hash

    # Get file name from last part of url
    file_name = url.split("/")[-1]
    cp(f"Downloading {file_name}...")

    with TemporaryDirectory() as temp_dir:
        temp_file = Path(temp_dir, file_name)
        with httpx.stream("GET", url) as r:
            r.raise_for_status()
            with temp_file.open("wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)

        hash_blake3 = blake3_hash_file(temp_file)
        cp(f"Blake3 Hash: {hash_blake3}")

    # Call manual
    publish_manual(
        version=version,
        url=url,
        changelog=changelog,
        hash_blake3=hash_blake3,
        channel=channel,
        update_type=update_type,
        b2_path=b2_path,
    )


@app.command()
def publish_manual(
        version: str,
        url: str,
        changelog: str,
        hash_blake3: str,
        channel: str = "stable",
        update_type: UpdateType = 1,
        b2_path: str = "update.json",
):
    """Publishes an update"""
    release_date = datetime.utcnow()
    cp(f"New Release Date: {release_date}")

    # Make signature
    cp("Signing update...")
    signature = sign_update(
        version=version,
        release_date=release_date,
        channel=channel,
        type=update_type,
        url=url,
        changelog=changelog,
        hash_blake3=hash_blake3,
    )
    cp(f"Created Signature: {signature!r}")

    info = UpdateInfo(
        version=version,
        releaseDate=release_date,
        channel=channel,
        url=url,
        changelog=changelog,
        hashBlake3=hash_blake3,
        signature=signature,
        type=update_type,
    )

    # Print and ask for confirmation
    json = info.model_dump_json(indent=4)
    cp(f"Update Info JSON: {json}")

    if not typer.confirm("Publish update?"):
        raise typer.Abort()

    # Save json to a temporary file
    with TemporaryDirectory() as temp_dir:
        temp_file = Path(temp_dir, "update.json")
        temp_file.write_text(json)

        # Upload file
        cp("Uploading...")
        uploader = Uploader(env.b2_api_id, env.b2_api_key, env.b2_bucket_name)
        uploader.upload(temp_file, b2_path)

        with RichProgressListener("Uploading...", transient=True) as pbar:
            uploader.upload(temp_file, b2_path, pbar)

    typer.echo("Updating Cloudflare cache...")
    cache_purge(urljoin(env.cdn_root, b2_path))

    result = urljoin(env.cdn_root, b2_path)
    typer.echo(f"✅  Uploaded at: {result!r}")


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
