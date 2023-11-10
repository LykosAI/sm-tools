"""Cloudflare API tools."""
from stability_matrix_tools.utils.cf_cache import cache_purge

import rich
import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def purge(url: str):
    """Purge a URL from Cloudflare's cache."""
    typer.echo(f"Purging {url!r} from Cloudflare's cache...")
    res = cache_purge(url)
    typer.echo(f"✅  ({res.status_code})")
    rich.print_json(res.text)
