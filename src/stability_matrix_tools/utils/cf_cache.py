"""Cloudflare cache management."""
from stability_matrix_tools.models.settings import env

import httpx
import requests


def cache_purge(*url: str) -> httpx.Response | None:
    """Purge URLs from Cloudflare's cache."""
    if not url:
        return None
    api_url = f"https://api.cloudflare.com/client/v4/zones/{env.cf_zone_id}/purge_cache"
    headers = {
        "Authorization": f"Bearer {env.cf_cache_purge_token}",
    }
    payload = {"files": list(url)}
    res = httpx.post(api_url, headers=headers, json=payload)
    res.raise_for_status()
    return res
