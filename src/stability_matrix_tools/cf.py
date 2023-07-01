"""Cloudflare API tools."""
from stability_matrix_tools.utils.cf_cache import cache_purge

import typer

app = typer.Typer()


@app.command()
def purge(url: str):
    """Purge a URL from Cloudflare's cache."""
    typer.echo(f"Purging {url!r} from Cloudflare's cache...")
    res = cache_purge(url)
    typer.echo(f"✅  Cache Purge Successful ({res.status_code})")
