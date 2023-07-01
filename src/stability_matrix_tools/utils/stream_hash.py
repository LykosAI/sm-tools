import os
from pathlib import Path

from rich.progress import Progress

from blake3 import blake3


def blake3_hash_file(file_path: str | Path):
    """Streamed md5 with progress bar."""
    hasher = blake3()
    filesize = os.path.getsize(file_path)
    desc = f"Computing blake3 hash of {os.path.basename(file_path)}"

    with Progress() as pbar:
        task = pbar.add_task(desc, total=filesize)

        chunk_size = 4096
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                hasher.update(chunk)
                pbar.update(task, advance=len(chunk))
        pbar.stop_task(task)

    return hasher.hexdigest()
