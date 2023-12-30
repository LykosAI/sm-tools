"""Manages automatic updates"""
import base64
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional
from urllib.parse import quote, urljoin

import httpx
import typer
from httpx import HTTPStatusError
from rich import print as cp
from rich import print_json
from rich.progress import track
from typing_extensions import Annotated

from stability_matrix_tools import b2
from stability_matrix_tools.models.settings import env
from stability_matrix_tools.models.update_base import UpdateChannel
from stability_matrix_tools.models.update_info import (
    UpdateCollection,
    UpdateInfo,
    UpdateType,
)
from stability_matrix_tools.models.update_info_v3 import UpdateManifest, UpdatePlatforms
from stability_matrix_tools.utils import signing, uris
from stability_matrix_tools.utils.cf_cache import cache_purge
from stability_matrix_tools.utils.console_diff import print_diff
from stability_matrix_tools.utils.progress import RichProgressListener
from stability_matrix_tools.utils.stream_hash import blake3_hash_file
from stability_matrix_tools.utils.uploader import Uploader

app = typer.Typer(no_args_is_help=True)


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


def validate_platform(platform: str) -> str:
    if platform not in ("win-x64", "linux-x64"):
        raise ValueError(f"Unknown platform: {platform!r}")
    return platform


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
            release_date.replace(tzinfo=timezone.utc).isoformat(),
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


def get_cdn_url(b2_path: str, bucket_name: str) -> str:
    # If bucket name is not default, add it to the url
    if bucket_name == "lykos-1":
        return uris.join(env.cdn_root, quote(b2_path))
    else:
        return uris.join(env.cdn_root, bucket_name, quote(b2_path))


@app.command()
def publish_matrix(
    version: Annotated[str, typer.Option("--version", "-v")],
    channel: Annotated[str, typer.Option("--channel")] = "stable",
    update_type_value: Annotated[str, typer.Option("--type")] = "normal",
    b2_path: Annotated[str, typer.Option("--b2-path")] = "update-v2.json",
    confirm: Annotated[bool, typer.Option("--yes", "-y")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
):
    """Publishes multiple updates for supported platforms"""
    update_type = UpdateType.parse(update_type_value)

    release_date = datetime.utcnow()
    cp(f"New Release Date: {release_date}")

    version_str = f"v{version}"

    # Create update info for each platform
    platform_infos: dict[str, UpdateInfo] = {}

    for platform, url in (
        (
            "win-x64",
            f"https://github.com/LykosAI/StabilityMatrix/releases/download/{version_str}/StabilityMatrix.exe",
        ),
        (
            "linux-x64",
            f"https://github.com/LykosAI/StabilityMatrix/releases/download/{version_str}/StabilityMatrix.AppImage",
        ),
    ):
        cp(f"Platform: {platform}")
        hash_blake3 = get_blake3_hash(url)

        changelog = f"https://cdn.jsdelivr.net/gh/LykosAI/StabilityMatrix@{version_str}/CHANGELOG.md"

        info = UpdateInfo(
            version=version,
            releaseDate=release_date,
            channel=channel,
            url=url,
            changelog=changelog,
            hashBlake3=hash_blake3,
            type=update_type,
            signature="",
        )

        # Make signature
        platform_infos[platform] = sign_update_info(info)

    # Fetch current json first to update a single platform
    current_collection = get_current_update_json(urljoin(env.cdn_root, b2_path))
    current_collection.win_x64 = platform_infos["win-x64"]
    current_collection.linux_x64 = platform_infos["linux-x64"]

    # Print and ask for confirmation
    json = current_collection.model_dump_json(indent=4, by_alias=True)
    cp("Update Info JSON:")
    print_json(json)

    if dry_run or (not confirm and not typer.confirm("Publish update?")):
        raise typer.Abort()

    upload_json(json, b2_path)


@app.command(no_args_is_help=True)
def publish_matrix_v3(
    version: Annotated[str, typer.Option("--version", "-v")],
    channel: Annotated[str, typer.Option("--channel")] = "stable",
    update_type_value: Annotated[str, typer.Option("--type")] = "normal",
    b2_path: Annotated[str, typer.Option("--b2-path")] = "update-v3.json",
    confirm: Annotated[bool, typer.Option("--yes", "-y")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
):
    """Publishes multiple update v3 for supported platforms"""
    version_str = f"v{version}"
    changelog = f"https://cdn.jsdelivr.net/gh/LykosAI/StabilityMatrix@{version_str}/CHANGELOG.md"
    cp(f"changelog url: {changelog}")

    github_base_url = "https://github.com/LykosAI/StabilityMatrix/releases/download/"

    platforms = {
        "win-x64": {
            "url": uris.join(
                github_base_url, version_str, "StabilityMatrix-win-x64.zip"
            ),
            "hash": "",
        },
        "linux-x64": {
            "url": uris.join(
                github_base_url, version_str, "StabilityMatrix-linux-x64.zip"
            ),
            "hash": "",
        },
        "macos-arm64": {
            "url": uris.join(
                github_base_url, version_str, "StabilityMatrix-macos-arm64.dmg"
            ),
            "hash": "",
        },
    }

    # Populate hashes
    for platform_id, platform in platforms.items():
        platform["hash"] = get_blake3_hash(platform["url"])

    publish_platforms_v3(
        version=version,
        changelog=changelog,
        channel_value=channel,
        update_type_value=update_type_value,
        win_x64=(
            platforms["win-x64"]["url"],
            platforms["win-x64"]["hash"],
        ),
        linux_x64=(
            platforms["linux-x64"]["url"],
            platforms["linux-x64"]["hash"],
        ),
        macos_arm64=(
            platforms["macos-arm64"]["url"],
            platforms["macos-arm64"]["hash"],
        ),
        b2_path=b2_path,
        confirm=confirm,
        dry_run=dry_run,
    )


@app.command()
def publish(
    platform: Annotated[str, typer.Option("--platform", "-p")],
    version: Annotated[str, typer.Option("--version", "-v")],
    url: Annotated[str, typer.Option("--url", "-u")],
    changelog: Annotated[str, typer.Option("--changelog")],
    channel: Annotated[str, typer.Option("--channel")] = "stable",
    update_type_value: Annotated[str, typer.Option("--type")] = "normal",
    b2_path: Annotated[str, typer.Option("--b2-path")] = "update-v2.json",
    confirm: Annotated[bool, typer.Option("--yes", "-y")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
):
    """Publishes an update"""
    validate_platform(platform)
    update_type = UpdateType.parse(update_type_value)

    # Get hash
    hash_blake3 = get_blake3_hash(url)

    # Call manual
    publish_manual(
        platform=platform,
        version=version,
        url=url,
        changelog=changelog,
        hash_blake3=hash_blake3,
        channel=channel,
        update_type=update_type,
        b2_path=b2_path,
        confirm=confirm,
        dry_run=dry_run,
    )


@app.command()
def publish_manual(
    platform: str,
    version: str,
    url: str,
    changelog: str,
    hash_blake3: str,
    channel: str = "stable",
    update_type_value: Annotated[str, typer.Option("--type")] = "normal",
    b2_path: str = "update-v2.json",
    confirm: Annotated[bool, typer.Option("--yes", "-y")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
):
    """Publishes an update"""
    validate_platform(platform)
    update_type = UpdateType.parse(update_type_value)

    release_date = datetime.utcnow()
    cp(f"New Release Date: {release_date}")

    info = UpdateInfo(
        version=version,
        releaseDate=release_date,
        channel=channel,
        url=url,
        changelog=changelog,
        hashBlake3=hash_blake3,
        type=update_type,
    )

    # Make signature
    info = sign_update_info(info)

    # Fetch current json first to update a single platform
    current_collection = get_current_update_json(urljoin(env.cdn_root, b2_path))

    # Update collection
    if platform == "win-x64":
        current_collection.win_x64 = info
    elif platform == "linux-x64":
        current_collection.linux_x64 = info
    else:
        raise ValueError(f"Unknown platform: {platform!r}")

    # Print and ask for confirmation
    json = current_collection.model_dump_json(indent=4, by_alias=True)
    cp("Update Info JSON:")
    print_json(json)

    if dry_run or (not confirm and not typer.confirm("Publish update?")):
        raise typer.Abort()

    upload_json(json, b2_path)


@app.command(no_args_is_help=True)
def publish_platforms_v3(
    version: Annotated[str, typer.Option("--version", "-v")],
    changelog: Annotated[str, typer.Option("--changelog")],
    channel_value: Annotated[str, typer.Option("--channel")] = "stable",
    update_type_value: Annotated[str, typer.Option("--type")] = "normal",
    win_x64: Annotated[
        Optional[tuple[str, str]], typer.Option("--win-x64", help="(url, hashBlake3)")
    ] = (None, None),
    linux_x64: Annotated[
        Optional[tuple[str, str]], typer.Option("--linux-x64", help="(url, hashBlake3)")
    ] = (None, None),
    macos_arm64: Annotated[
        Optional[tuple[str, str]], typer.Option("--macos-arm64", help="(url, hashBlake3)")
    ] = (None, None),
    b2_path: Annotated[str, typer.Option("--b2-path")] = "update-v3.json",
    confirm: Annotated[bool, typer.Option("--yes", "-y")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
):
    """Publishes a v3 update"""

    platforms = {
        "win-x64": win_x64,
        "linux-x64": linux_x64,
        "macos-arm64": macos_arm64,
    }
    cp(f"platforms: {platforms}")

    if not win_x64[0] and not linux_x64[0] and not macos_arm64[0]:
        raise ValueError("No platforms specified")

    update_type = UpdateType.parse(update_type_value)
    channel = UpdateChannel(channel_value)

    release_date = datetime.utcnow()
    cp(f"New Release Date: {release_date}")

    # Get current manifest
    current_manifest = get_current_update_v3_json(uris.join(env.cdn_root, b2_path))

    # Check if we will replace any previous updates
    if channel in current_manifest.updates:
        to_replace = current_manifest.updates[channel]
        cp(
            f"The previous update ({to_replace.win_x64.version}, {to_replace.linux_x64.version}) will be removed by this operation"
        )

    # New platform update
    new_platforms_dict = {}

    # Add platforms
    for platform_id, (update_url, update_hash) in platforms.items():
        if not update_url:
            continue
        if not update_hash:
            raise ValueError(
                f"Missing hash for {platform_id}: {platforms[platform_id]}"
            )

        info = UpdateInfo(
            version=version,
            releaseDate=release_date,
            channel=channel,
            url=update_url,
            changelog=changelog,
            hashBlake3=update_hash,
            type=update_type,
            signature="",
        )
        info = sign_update_info(info)

        new_platforms_dict[platform_id] = info

    new_platforms = UpdatePlatforms(**new_platforms_dict)

    # Show replacement changes
    if channel in current_manifest.updates:
        cp(f"Removed for {channel}:")
        print_json(
            current_manifest.updates[channel].model_dump_json(indent=2, by_alias=True)
        )

    cp(f"Added for {channel}:")
    print_json(new_platforms.model_dump_json(indent=2, by_alias=True))

    # replace current
    new_manifest = current_manifest.model_copy(deep=True)
    new_manifest.updates[channel] = new_platforms

    cp("Update Manifest Diff:")
    print_diff(
        current_manifest.model_dump_json(indent=2, by_alias=True),
        new_manifest.model_dump_json(indent=2, by_alias=True),
    )

    if dry_run or (not confirm and not typer.confirm(f"Publish update to {b2_path}?")):
        raise typer.Abort()

    upload_json(new_manifest.model_dump_json(indent=2, by_alias=True), b2_path)


@app.command(no_args_is_help=True)
def publish_files_v3(
    version: Annotated[str, typer.Option("--version", "-v")],
    changelog: Annotated[
        Path, typer.Option("--changelog", help="File path to changelog")
    ],
    channel_value: Annotated[str, typer.Option("--channel")] = "stable",
    update_type_value: Annotated[str, typer.Option("--type")] = "normal",
    win_x64: Annotated[
        Optional[Path], typer.Option("--win-x64", help="File path to win-x64 update")
    ] = None,
    linux_x64: Annotated[
        Optional[Path],
        typer.Option("--linux-x64", help="File path to linux-x64 update"),
    ] = None,
    macos_arm64: Annotated[
        Optional[Path],
        typer.Option("--macos-arm64", help="File path to macos-arm64 update"),
    ] = None,
    b2_bucket_name: Annotated[
        str, typer.Option("--b2-bucket-name")
    ] = env.b2_bucket_secure_name,
    b2_manifest_path: Annotated[
        str, typer.Option("--b2-manifest-path")
    ] = "update-v3.json",
    confirm: Annotated[bool, typer.Option("--yes", "-y")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
):
    """Publishes a v3 update with files"""

    if not win_x64 and not linux_x64 and not macos_arm64:
        raise ValueError("No platforms specified")

    platforms = {
        "win-x64": {
            "path": win_x64 and win_x64.resolve(),
            "url": "",
            "hash": "",
        },
        "linux-x64": {
            "path": linux_x64 and linux_x64.resolve(),
            "url": "",
            "hash": "",
        },
        "macos-arm64": {
            "path": macos_arm64 and macos_arm64.resolve(),
            "url": "",
            "hash": "",
        },
    }

    # Populate hashes
    for platform_id, platform in platforms.items():
        if not platform["path"]:
            continue

        platform["hash"] = blake3_hash_file(platform["path"])

    # default path is
    # /sm/v{version}/CHANGELOG.md
    # /sm/v{version}/StabilityMatrix-{platform}.zip

    # Changelog goes to main bucket
    changelog_b2_path = f"sm/v{version}/{changelog.name}"
    b2.upload(changelog, changelog_b2_path, env.b2_bucket_name)
    changelog_url = get_cdn_url(changelog_b2_path, env.b2_bucket_name)

    # Downloads go to selected bucket
    for platform_id, platform in platforms.items():
        if not platform["path"]:
            continue

        # Set b2 path
        platform["b2_path"] = f"sm/v{version}/{platform['path'].name}"
        # Upload file
        b2.upload(platform["path"], platform["b2_path"], b2_bucket_name)
        # Add url to platform
        platform["url"] = get_cdn_url(platform["b2_path"], b2_bucket_name)

    cp(f"platforms: {platforms}")

    try:
        publish_platforms_v3(
            version=version,
            changelog=changelog_url,
            channel_value=channel_value,
            update_type_value=update_type_value,
            win_x64=(
                platforms["win-x64"]["url"],
                platforms["win-x64"]["hash"],
            ),
            linux_x64=(
                platforms["linux-x64"]["url"],
                platforms["linux-x64"]["hash"],
            ),
            macos_arm64=(
                platforms["macos-arm64"]["url"],
                platforms["macos-arm64"]["hash"],
            ),
            b2_path=b2_manifest_path,
            confirm=confirm,
            dry_run=dry_run,
        )
    except Exception as e:
        cp(f"❌  Error: {e}")
        cp("Cleaning up...")

        # Delete files
        b2.delete(changelog_b2_path, env.b2_bucket_name)

        for platform_id, platform in platforms.items():
            if "b2_path" in platform:
                b2.delete(platform["b2_path"], b2_bucket_name)

        raise typer.Abort()


def sign_update_info(info: UpdateInfo) -> UpdateInfo:
    cp("Signing update...")
    signature = sign_update(
        version=info.version,
        release_date=info.release_date,
        channel=info.channel.value,
        type=info.type,
        url=info.url,
        changelog=info.changelog,
        hash_blake3=info.hash_blake3,
    )
    cp(f"Created Signature: {signature!r}")

    info.signature = signature
    return info


def get_blake3_hash(file_url: str) -> str:
    file_name = file_url.split("/")[-1]

    if not file_name:
        raise ValueError(f"Invalid file url, file name not found: {file_url!r}")

    desc = f"Downloading {file_name}..."

    header_resp = httpx.head(file_url, follow_redirects=True)
    header_resp.raise_for_status()
    total = int(header_resp.headers["Content-Length"])
    chunk_size = 1024 * 1024

    with TemporaryDirectory() as temp_dir:
        temp_file = Path(temp_dir, file_name)
        with httpx.stream("GET", file_url, follow_redirects=True) as r:
            r.raise_for_status()
            with temp_file.open("wb") as f:
                for chunk in track(
                    r.iter_bytes(chunk_size), description=desc, total=total / chunk_size
                ):
                    f.write(chunk)

        hash_blake3 = blake3_hash_file(temp_file)
        cp(f"Blake3 Hash: {hash_blake3}")

    return hash_blake3


def upload_json(json: str, b2_path: str):
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


def get_current_update_json(url: str) -> UpdateCollection:
    cp("Fetching current manifest...")

    try:
        response = httpx.get(url, headers={"Cache-Control": "no-cache"})
        response.raise_for_status()

        cp(f"✅  {url!r} -> ({response.status_code})")

        current_collection = UpdateCollection.model_validate_json(response.text)

        if current_collection.win_x64 is not None:
            cp(f"Current win-x64: {current_collection.win_x64.version}")
        if current_collection.linux_x64 is not None:
            cp(f"Current linux-x64: {current_collection.linux_x64.version}")
        if current_collection.macos_arm64 is not None:
            cp(f"Current macos-arm64: {current_collection.macos_arm64.version}")

    except HTTPStatusError as e:
        cp(f"Skipped current manifest ({e.response.status_code})")

        # Create empty collection
        current_collection = UpdateCollection()

    return current_collection


def get_current_update_v3_json(url: str) -> UpdateManifest:
    cp("Fetching current v3 manifest...")

    try:
        response = httpx.get(url, headers={"Cache-Control": "no-cache"})
        response.raise_for_status()

        cp(f"✅  {url!r} -> ({response.status_code})")

        current_manifest = UpdateManifest.model_validate_json(response.text)
    except HTTPStatusError as e:
        cp(f"Skipped current manifest ({e.response.status_code})")
        # Create empty collection
        current_manifest = UpdateManifest()

    return current_manifest


@app.command()
def check_v3(b2_path: str = "update-v3.json"):
    """Checks for updates"""

    cp("Checking for updates...")

    url = urljoin(env.cdn_root, b2_path)
    # Use a cache-control 0 header to ensure we get the latest version
    res = httpx.get(url, headers={"Cache-Control": "no-cache"})
    try:
        res.raise_for_status()
    except HTTPStatusError as e:
        cp(f"❌  {url!r} -> ({e.response.status_code})")
        return

    cp(f"✅  {url!r} -> ({res.status_code})")
    cp(res.json())

    updates = UpdateManifest.model_validate_json(res.text)
    cp(updates)


@app.command()
def check(b2_path: str = "update-v2.json"):
    """Checks for updates"""

    cp("Checking for updates...")

    url = urljoin(env.cdn_root, b2_path)
    # Use a cache-control 0 header to ensure we get the latest version
    res = httpx.get(url, headers={"Cache-Control": "no-cache"})
    try:
        res.raise_for_status()
    except HTTPStatusError as e:
        cp(f"❌  {url!r} -> ({e.response.status_code})")
        return

    cp(f"✅  {url!r} -> ({res.status_code})")
    cp(res.json())

    updates = UpdateInfo.model_validate_json(res.text)
    cp(updates)
